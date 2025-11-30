# intent_handlers.py
"""
JARVIS Intent Handlers

Handles routing and execution of different intent types.
Extracted from jarvis_core.py to improve modularity.

Intent types:
- conversation: Casual chat
- query: Knowledge questions
- crud_create: Create memory records
- crud_read: Read memory records
- crud_update: Update memory records
- crud_delete: Delete memory records
- smarthome: Smart home control
- system: System commands
"""

from typing import Dict, Optional, Callable
from datetime import datetime


class IntentHandlers:
    """
    Routes intents to appropriate handlers and executes them.
    
    Responsibilities:
    - Route intents to correct handler methods
    - Execute CRUD operations on memory
    - Generate conversational responses
    - Handle knowledge queries
    - Manage smart home commands
    """
    
    def __init__(self, jarvis_core):
        """
        Initialize with reference to JarvisCore
        
        Args:
            jarvis_core: Main JARVIS instance for accessing state
        """
        self.core = jarvis_core
        
        # Register intent handlers
        self.handlers: Dict[str, Callable] = {
            "crud_create": self.handle_crud_create,
            "crud_read": self.handle_crud_read,
            "crud_update": self.handle_crud_update,
            "crud_delete": self.handle_crud_delete,
            "smarthome": self.handle_smarthome,
            "query": self.handle_query,
            "conversation": self.handle_conversation,
        }
        
        # Statistics
        self.stats = {
            "total_handled": 0,
            "by_intent": {},
            "failures": 0
        }
    
    # ==================== ROUTING ====================
    
    async def route(
        self,
        intent: str,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """
        Route intent to appropriate handler
        
        Args:
            intent: Intent type (e.g., "query", "crud_create")
            entities: Extracted entities
            original_input: Original user input
            context: Conversation context
            
        Returns:
            Response string
        """
        
        self.core._log("HANDLER", f"Routing intent: {intent}")
        
        # Update statistics
        self.stats["total_handled"] += 1
        self.stats["by_intent"][intent] = self.stats["by_intent"].get(intent, 0) + 1
        
        # Get handler
        handler = self.handlers.get(intent)
        
        if not handler:
            self.core._log("HANDLER", f"No handler for intent: {intent}")
            return "I'm not sure how to help with that yet."
        
        try:
            # Execute handler
            response = await handler(entities, original_input, context)
            return response
            
        except Exception as e:
            self.stats["failures"] += 1
            self.core._log("ERROR", f"Handler failed for {intent}: {e}")
            import traceback
            traceback.print_exc()
            return f"I had trouble processing that request. ({str(e)})"
    
    # ==================== CRUD HANDLERS ====================
    
    async def handle_crud_create(
        self,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """Create a new record in memory"""
        
        if not self.core.memory_store:
            return "Memory system not initialized."
        
        # SAFEGUARD: Don't create contact from single word with no details
        words = original_input.strip().split()
        has_details = (entities.get("phone") or entities.get("email") or 
                      entities.get("company") or entities.get("content") or
                      len(words) > 3)
        
        if len(words) <= 2 and not has_details:
            # Likely misclassified - this might be a lookup attempt
            name = words[0] if words else original_input
            return f"Did you want to look up information about {name}, or create a new contact? If creating, please provide details like: 'Save {name}, phone 555-1234'"
        
        record_type = entities.get("type", "note")
        
        try:
            if record_type == "contact":
                return await self._create_contact(entities)
            
            elif record_type == "calendar":
                return await self._create_calendar_event(entities)
            
            else:  # Default to note
                return await self._create_note(entities, original_input)
        
        except Exception as e:
            self.core._log("ERROR", f"CRUD create failed: {e}")
            return f"I had trouble saving that. {str(e)}"
    
    async def _create_contact(self, entities: Dict) -> str:
        """Create a contact record"""
        name = entities.get("name", "")
        if not name:
            return "I need a name to create a contact."
        
        contact_id = self.core.memory_store.create_contact(
            name=name,
            phone_home=entities.get("phone_home"),
            phone_work=entities.get("phone_work"),
            phone_mobile=entities.get("phone") or entities.get("phone_mobile"),
            email_personal=entities.get("email") or entities.get("email_personal"),
            email_work=entities.get("email_work"),
            company=entities.get("company"),
            title=entities.get("title"),
            notes=entities.get("notes")
        )
        
        self.core._log("MEMORY", f"Created contact: {name} (ID: {contact_id})")
        return f"Got it! I've saved {name}'s contact information."
    
    async def _create_calendar_event(self, entities: Dict) -> str:
        """Create a calendar event"""
        title = entities.get("title", "")
        start = entities.get("date") or entities.get("start_datetime")
        
        if not title or not start:
            return "I need a title and date/time to create a calendar event."
        
        # Parse datetime
        start_datetime = self._parse_datetime(start, entities.get("time"))
        
        event_id = self.core.memory_store.create_event(
            title=title,
            start_datetime=start_datetime,
            location=entities.get("location"),
            description=entities.get("description") or entities.get("content"),
            attendees=entities.get("attendees", "").split(",") if entities.get("attendees") else None
        )
        
        self.core._log("MEMORY", f"Created event: {title} (ID: {event_id})")
        return f"I've added '{title}' to your calendar for {start_datetime}."
    
    async def _create_note(self, entities: Dict, original_input: str) -> str:
        """Create a note record"""
        title = entities.get("title") or entities.get("name") or original_input[:50]
        content = entities.get("content") or original_input
        
        note_id = self.core.memory_store.create_note(
            title=title,
            content=content,
            tags=["aide-memoire"]
        )
        
        self.core._log("MEMORY", f"Created note: {title} (ID: {note_id})")
        return f"I've noted that: {title}"
    
    async def handle_crud_read(
        self,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """Read records from memory"""
        
        if not self.core.memory_store:
            return "Memory system not initialized."
        
        record_type = entities.get("type", "contact")
        identifier = entities.get("identifier", "")
        field = entities.get("field", "all")
        
        # ENHANCEMENT: If identifier is empty OR is a list keyword, treat as list all
        if not identifier or identifier.lower() in ["all", "contacts", "everyone", "list"]:
            identifier = ""  # Empty means list all
        
        # If identifier is still not empty, try to improve extraction
        if not identifier:
            # Try to find a name in the input
            words = original_input.lower().split()
            
            # Remove common words including list/all keywords
            common_words = ["what", "is", "the", "a", "an", "about", "tell", "me", 
                           "who", "when", "where", "show", "list", "all", "my",
                           "contact", "contacts", "number", "phone", "email"]
            potential_names = [w.strip("?.,!") for w in words if w not in common_words]
            
            # Look for possessive patterns (bob's, sarah's)
            for word in words:
                if "'s" in word or "s'" in word:
                    identifier = word.replace("'s", "").replace("s'", "").strip("?.,!")
                    break
            
            # If still no identifier, try first capitalized word or last non-common word
            if not identifier and potential_names:
                identifier = potential_names[-1]  # Take last meaningful word
        
        self.core._log("HANDLER", f"CRUD read: type={record_type}, identifier='{identifier}', field={field}")
        
        try:
            if record_type == "contact":
                return await self._read_contact(identifier, field)
            
            elif record_type == "calendar":
                return await self._read_calendar_events(identifier)
            
            elif record_type == "note":
                return await self._read_notes(identifier)
            
            return "Search not yet implemented for this type."
        
        except Exception as e:
            self.core._log("ERROR", f"CRUD read failed: {e}")
            return f"I had trouble looking that up. {str(e)}"
    
    async def _read_contact(self, identifier: str, field: str) -> str:
        """Read contact information"""
        
        # Special case: list all contacts
        if not identifier or identifier in ["all", "contacts", "everyone"]:
            # Use find_contacts with empty string to get all
            all_contacts = self.core.memory_store.find_contacts("")
            
            if not all_contacts:
                return "You don't have any contacts saved."
            
            if len(all_contacts) <= 10:
                # Show all
                lines = [f"You have {len(all_contacts)} contact(s):"]
                for c in all_contacts:
                    phone = c.get('phone_mobile') or c.get('phone_home') or 'no phone'
                    lines.append(f"  • {c['name']}: {phone}")
                return "\n".join(lines)
            else:
                # Show summary
                names = [c['name'] for c in all_contacts[:10]]
                return f"You have {len(all_contacts)} contacts. First 10: {', '.join(names)}..."
        
        # Normal lookup
        contacts = self.core.memory_store.find_contacts(identifier)
        
        if not contacts:
            return f"I don't have any contacts matching '{identifier}'."
        
        if len(contacts) == 1:
            contact = contacts[0]
            
            # If asking for specific field
            if field not in ["all", "info", "information"]:
                # Try to find the field value
                value = (contact.get(field) or 
                        contact.get(f"{field}_mobile") or 
                        contact.get(f"{field}_personal") or
                        contact.get(f"phone_{field}") or
                        contact.get(f"email_{field}"))
                
                if value:
                    return f"{contact['name']}'s {field}: {value}"
                else:
                    return f"I don't have {field} for {contact['name']}."
            
            # Return full contact info
            info = [f"📇 {contact['name']}"]
            
            if contact.get('phone_mobile'):
                info.append(f"  📱 Mobile: {contact['phone_mobile']}")
            if contact.get('phone_work'):
                info.append(f"  ☎️  Work: {contact['phone_work']}")
            if contact.get('phone_home'):
                info.append(f"  🏠 Home: {contact['phone_home']}")
            if contact.get('email_personal'):
                info.append(f"  📧 Email: {contact['email_personal']}")
            if contact.get('company'):
                info.append(f"  🏢 Company: {contact['company']}")
            
            return "\n".join(info)
        
        else:
            # Multiple matches - show details to help disambiguate
            lines = [f"I found {len(contacts)} contacts matching '{identifier}':"]
            for i, c in enumerate(contacts[:5], 1):
                phone = c.get('phone_mobile') or c.get('phone_home') or 'no phone'
                company = c.get('company', '')
                extra = f" ({company})" if company else ""
                lines.append(f"  {i}. {c['name']}{extra}: {phone}")
            
            if len(contacts) > 5:
                lines.append(f"  ... and {len(contacts) - 5} more")
            
            lines.append("\nCan you be more specific? Or say 'the first one'")
            return "\n".join(lines)
    
    async def _read_calendar_events(self, identifier: str) -> str:
        """Read calendar events"""
        # TODO: Implement when calendar search is available
        return "Calendar search not yet implemented."
    
    async def _read_notes(self, identifier: str) -> str:
        """Read notes"""
        # TODO: Implement when note search is available
        return "Note search not yet implemented."
    
    async def handle_crud_update(
        self,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """Update a record in memory"""
        # TODO: Implement update functionality
        return "Update functionality coming soon..."
    
    async def handle_crud_delete(
        self,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """Delete a record from memory"""
        # TODO: Implement delete functionality
        return "Delete functionality coming soon..."
    
    # ==================== QUERY HANDLER ====================
    
    async def handle_query(
        self,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """Handle general knowledge queries using web search + LLM"""
        
        if not self.core.current_task:
            return "I'm not sure what you're asking about."
        
        question = self.core.current_task.content
        
        # Try web search first for factual queries
        if self.core.search_provider:
            self.core._log("QUERY", f"Searching web for: {question[:50]}...")
            
            try:
                search_results = self.core.search_provider.search(question, num_results=5)
                
                if search_results:
                    # Format results for LLM to synthesize
                    search_context = self._format_search_for_llm(search_results)
                    
                    # Ask LLM to synthesize answer from search results
                    synthesis_prompt = f"""Based on these search results, answer the question: {question}

    Search Results:
    {search_context}

    Provide a clear, concise answer based on the search results above. If the results don't contain enough information, say so."""

                    if self.core.prompt_manager:
                        result = await self.core.prompt_manager.generate_response(
                            user_input=synthesis_prompt,
                            intent="query",
                            entities=entities,
                            context=context
                        )
                        
                        if result.success and result.parsed_json:
                            answer = result.parsed_json.get("response", "")
                        elif result.success:
                            answer = result.response
                        else:
                            answer = None
                        
                        if answer:
                            # Add source attribution
                            sources = "\n\nSources:\n" + "\n".join([f"• {r.url}" for r in search_results[:3]])
                            return answer + sources
            
            except Exception as e:
                self.core._log("ERROR", f"Web search failed: {e}")
                # Fall through to LLM-only approach
        
        # Fallback: Use LLM without search
        if not self.core.prompt_manager:
            return "I don't have enough information to answer that."
        
        self.core._log("QUERY", f"Processing query with LLM only: {question[:50]}...")
        
        result = await self.core.prompt_manager.generate_response(
            user_input=question,
            intent="query",
            entities=entities,
            context=context
        )
        
        if result.success and result.parsed_json:
            return result.parsed_json.get("response", "I'm not sure.")
        elif result.success:
            return result.response
        else:
            return "I don't have enough information to answer that."

    def _format_search_for_llm(self, results) -> str:
        """Format search results for LLM context"""
        formatted = []
        for i, result in enumerate(results[:5], 1):
            formatted.append(f"{i}. {result.title}")
            formatted.append(f"   URL: {result.url}")
            formatted.append(f"   {result.snippet}")
            formatted.append("")
        
        return "\n".join(formatted)
    
    # ==================== CONVERSATION HANDLER ====================
    
    async def handle_conversation(
        self,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """Handle casual conversation"""
        
        if not self.core.prompt_manager:
            return "I'm here!"
        
        self.core._log("CHAT", f"Conversing: {original_input[:50]}...")
        
        result = await self.core.prompt_manager.generate_response(
            user_input=original_input,
            intent="conversation",
            entities=entities,
            context=context
        )
        
        if result.success and result.parsed_json:
            return result.parsed_json.get("response", "I understand.")
        elif result.success:
            return result.response
        else:
            return "I'm listening."
    
    # ==================== SMART HOME HANDLER ====================
    
    async def handle_smarthome(
        self,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """Handle smart home control commands"""
        
        device = entities.get("device", "device")
        action = entities.get("action", "control")
        
        self.core._log("SMARTHOME", f"Control request: {action} {device}")
        
        # TODO: Integrate with actual smart home APIs
        return f"Smart home control: {action} {device} (not yet connected)"
    
    # ==================== HELPER METHODS ====================
    
    def _parse_datetime(self, date_str: str, time_str: Optional[str] = None) -> str:
        """
        Parse date and time strings into ISO format
        
        Args:
            date_str: Date string (e.g., "2025-12-25", "tomorrow")
            time_str: Time string (e.g., "14:30", "2:30 PM")
            
        Returns:
            ISO format datetime string
        """
        
        # TODO: Implement proper date/time parsing
        # For now, return a simple format
        
        if time_str:
            return f"{date_str} {time_str}"
        else:
            return date_str
    
    def get_stats(self) -> Dict:
        """Get handler statistics"""
        
        return {
            **self.stats,
            "success_rate": (
                (self.stats["total_handled"] - self.stats["failures"]) / 
                max(self.stats["total_handled"], 1)
            )
        }