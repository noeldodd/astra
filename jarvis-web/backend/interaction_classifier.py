# interaction_classifier.py
"""
Intelligent Question Classifier

Analyzes JARVIS responses to classify questions by:
- Type (approval, information, choice, etc.)
- Risk level (low, medium, high, critical)
- Required interaction pattern
- Timeout behavior
"""

import re
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass


class RiskLevel(Enum):
    """Risk level of a question/decision"""
    LOW = "low"              # Preferences, non-critical info
    MEDIUM = "medium"        # Dates, names, clarifications
    HIGH = "high"            # Purchases, deletions, significant actions
    CRITICAL = "critical"    # Medical, financial, legal decisions


class QuestionType(Enum):
    """Type of interaction needed"""
    APPROVAL = "approval"              # Yes/No decision
    INFORMATION = "information"        # Need specific data
    CHOICE = "choice"                  # Multiple options
    CONFIRMATION = "confirmation"      # Confirm understanding
    OPEN_ENDED = "open_ended"         # Free-form response


class ExecutionMode(Enum):
    """How autonomous should execution be"""
    AUTONOMOUS = "autonomous"          # Just do it - no questions
    SUPERVISED = "supervised"          # Ask for major decisions only
    INTERACTIVE = "interactive"        # Ask for everything (default)
    APPROVAL_REQUIRED = "approval"     # Every step needs approval


@dataclass
class QuestionClassification:
    """Result of classifying a question"""
    type: QuestionType
    risk_level: RiskLevel
    timeout_ms: Optional[int]
    default_action: Optional[str]
    require_explicit: bool
    suggested_actions: List[str]
    disclaimer: Optional[str] = None
    warning_level: Optional[str] = None
    amount: Optional[float] = None
    domain: Optional[str] = None


class InteractionClassifier:
    """
    Classifies questions and determines interaction requirements
    """
    
    # Financial keywords
    FINANCIAL_KEYWORDS = [
        r'\$\d+', r'invest', r'purchase', r'buy', r'spend', r'cost',
        r'payment', r'transaction', r'transfer', r'stock', r'bond',
        r'account', r'withdraw', r'deposit'
    ]
    
    # Medical keywords
    MEDICAL_KEYWORDS = [
        r'medication', r'surgery', r'treatment', r'doctor', r'hospital',
        r'prescription', r'diagnosis', r'symptom', r'disease', r'medical',
        r'health', r'therapy', r'procedure'
    ]
    
    # Destructive keywords
    DESTRUCTIVE_KEYWORDS = [
        r'delete', r'remove', r'cancel', r'terminate', r'destroy',
        r'erase', r'wipe', r'drop', r'purge'
    ]
    
    # Legal keywords
    LEGAL_KEYWORDS = [
        r'contract', r'agreement', r'legal', r'lawsuit', r'court',
        r'attorney', r'liability', r'compliance', r'regulation'
    ]
    
    def classify(self, text: str, context: Optional[Dict] = None) -> QuestionClassification:
        """
        Classify a question/response from JARVIS
        
        Args:
            text: The response text to classify
            context: Optional context (plan info, user prefs, etc.)
            
        Returns:
            QuestionClassification with all metadata
        """
        
        text_lower = text.lower()
        context = context or {}
        
        # Check for critical domains first
        if self._is_medical(text_lower):
            return self._classify_medical(text, context)
        
        if self._is_financial(text_lower):
            return self._classify_financial(text, context)
        
        if self._is_legal(text_lower):
            return self._classify_legal(text, context)
        
        if self._is_destructive(text_lower):
            return self._classify_destructive(text, context)
        
        # Check for approval patterns
        if self._is_approval_request(text_lower):
            return self._classify_approval(text, context)
        
        # Check for information requests
        if self._is_information_request(text_lower):
            return self._classify_information(text, context)
        
        # Check for choices
        if self._is_choice_request(text_lower):
            return self._classify_choice(text, context)
        
        # Default: open-ended question
        return self._classify_open_ended(text, context)
    
    # ==================== DOMAIN DETECTION ====================
    
    def _is_medical(self, text: str) -> bool:
        """Check if question involves medical decisions"""
        return any(re.search(kw, text, re.I) for kw in self.MEDICAL_KEYWORDS)
    
    def _is_financial(self, text: str) -> bool:
        """Check if question involves financial decisions"""
        return any(re.search(kw, text, re.I) for kw in self.FINANCIAL_KEYWORDS)
    
    def _is_legal(self, text: str) -> bool:
        """Check if question involves legal matters"""
        return any(re.search(kw, text, re.I) for kw in self.LEGAL_KEYWORDS)
    
    def _is_destructive(self, text: str) -> bool:
        """Check if action is destructive"""
        return any(re.search(kw, text, re.I) for kw in self.DESTRUCTIVE_KEYWORDS)
    
    def _is_approval_request(self, text: str) -> bool:
        """Check if asking for approval/confirmation"""
        patterns = [
            r"reply ['\"]?yes['\"]? to proceed",
            r"reply ['\"]?yes['\"]? to confirm",
            r"approve|confirm",
            r"proceed\?",
            r"continue\?"
        ]
        return any(re.search(p, text, re.I) for p in patterns)
    
    def _is_information_request(self, text: str) -> bool:
        """Check if asking for specific information"""
        patterns = [
            r"what (date|time|when|where|who)",
            r"which (option|choice|one)",
            r"how (many|much|long)",
            r"please (provide|specify|enter|give)"
        ]
        return any(re.search(p, text, re.I) for p in patterns)
    
    def _is_choice_request(self, text: str) -> bool:
        """Check if presenting multiple choices"""
        # Look for numbered lists or bullet points
        has_numbers = re.search(r'\d+\.\s+\w+.*\d+\.\s+\w+', text)
        has_bullets = re.search(r'[•\-\*]\s+\w+.*[•\-\*]\s+\w+', text)
        has_or = re.search(r'\w+\s+or\s+\w+', text, re.I)
        
        return bool(has_numbers or has_bullets or has_or)
    
    # ==================== CLASSIFICATION METHODS ====================
    
    def _classify_medical(self, text: str, context: Dict) -> QuestionClassification:
        """Classify medical decision - CRITICAL risk"""
        return QuestionClassification(
            type=QuestionType.CONFIRMATION,
            risk_level=RiskLevel.CRITICAL,
            timeout_ms=None,  # No timeout
            default_action=None,
            require_explicit=True,
            suggested_actions=["I understand and want to continue", "Cancel this request"],
            disclaimer=(
                "⚠️ MEDICAL DISCLAIMER: This is AI-generated information only. "
                "Always consult with a licensed medical professional before making "
                "any health-related decisions."
            ),
            warning_level="critical",
            domain="medical"
        )
    
    def _classify_financial(self, text: str, context: Dict) -> QuestionClassification:
        """Classify financial decision - risk depends on amount"""
        
        # Extract amount if present
        amount = self._extract_amount(text)
        
        # High amounts = critical
        if amount and amount >= 1000:
            risk_level = RiskLevel.CRITICAL
            timeout_ms = None
            require_explicit = True
            disclaimer = (
                f"⚠️ FINANCIAL DECISION: This involves ${amount:,.2f}. "
                "Please review carefully."
            )
        elif amount and amount >= 100:
            risk_level = RiskLevel.HIGH
            timeout_ms = None
            require_explicit = True
            disclaimer = None
        else:
            risk_level = RiskLevel.MEDIUM
            timeout_ms = 120000  # 2 minutes
            require_explicit = False
            disclaimer = None
        
        return QuestionClassification(
            type=QuestionType.APPROVAL,
            risk_level=risk_level,
            timeout_ms=timeout_ms,
            default_action="cancel" if require_explicit else "ask_again",
            require_explicit=require_explicit,
            suggested_actions=["Approve", "Cancel", "Tell me more"],
            disclaimer=disclaimer,
            amount=amount,
            domain="financial"
        )
    
    def _classify_legal(self, text: str, context: Dict) -> QuestionClassification:
        """Classify legal decision - HIGH/CRITICAL risk"""
        return QuestionClassification(
            type=QuestionType.CONFIRMATION,
            risk_level=RiskLevel.CRITICAL,
            timeout_ms=None,
            default_action=None,
            require_explicit=True,
            suggested_actions=["I understand and proceed", "Cancel", "Consult attorney"],
            disclaimer=(
                "⚠️ LEGAL MATTER: This involves legal considerations. "
                "Consider consulting with a licensed attorney."
            ),
            domain="legal"
        )
    
    def _classify_destructive(self, text: str, context: Dict) -> QuestionClassification:
        """Classify destructive action - HIGH risk"""
        return QuestionClassification(
            type=QuestionType.CONFIRMATION,
            risk_level=RiskLevel.HIGH,
            timeout_ms=None,
            default_action=None,
            require_explicit=True,
            suggested_actions=["Yes, I'm sure", "No, cancel"],
            warning_level="high",
            disclaimer="⚠️ This action may be irreversible. Please confirm."
        )
    
    def _classify_approval(self, text: str, context: Dict) -> QuestionClassification:
        """Classify general approval request - MEDIUM risk"""
        
        # Check if it mentions steps/API calls
        has_plan_details = re.search(r'(\d+)\s+steps?', text, re.I)
        has_api_calls = re.search(r'(\d+)\s+api\s+calls?', text, re.I)
        
        if has_plan_details or has_api_calls:
            # Plan execution approval
            return QuestionClassification(
                type=QuestionType.APPROVAL,
                risk_level=RiskLevel.MEDIUM,
                timeout_ms=120000,  # 2 minutes
                default_action="cancel",
                require_explicit=False,
                suggested_actions=["Yes, proceed", "No, cancel", "Modify plan"]
            )
        else:
            # General approval
            return QuestionClassification(
                type=QuestionType.APPROVAL,
                risk_level=RiskLevel.LOW,
                timeout_ms=60000,  # 1 minute
                default_action="yes",
                require_explicit=False,
                suggested_actions=["Yes", "No"]
            )
    
    def _classify_information(self, text: str, context: Dict) -> QuestionClassification:
        """Classify information request - LOW/MEDIUM risk"""
        
        text_lower = text.lower()
        
        # Check what kind of information
        if 'date' in text_lower or 'when' in text_lower:
            input_type = "date"
        elif 'name' in text_lower or 'who' in text_lower:
            input_type = "text"
        elif 'how many' in text_lower or 'how much' in text_lower:
            input_type = "number"
        else:
            input_type = "text"
        
        return QuestionClassification(
            type=QuestionType.INFORMATION,
            risk_level=RiskLevel.LOW,
            timeout_ms=30000,  # 30 seconds
            default_action="skip",
            require_explicit=False,
            suggested_actions=["Submit", "Skip"],
            domain=input_type
        )
    
    def _classify_choice(self, text: str, context: Dict) -> QuestionClassification:
        """Classify multiple choice - LOW risk"""
        
        # Extract choices
        choices = self._extract_choices(text)
        
        return QuestionClassification(
            type=QuestionType.CHOICE,
            risk_level=RiskLevel.LOW,
            timeout_ms=60000,  # 1 minute
            default_action="first",
            require_explicit=False,
            suggested_actions=choices or ["Option 1", "Option 2", "Other"]
        )
    
    def _classify_open_ended(self, text: str, context: Dict) -> QuestionClassification:
        """Classify open-ended question - MEDIUM risk"""
        return QuestionClassification(
            type=QuestionType.OPEN_ENDED,
            risk_level=RiskLevel.MEDIUM,
            timeout_ms=120000,  # 2 minutes
            default_action="skip",
            require_explicit=False,
            suggested_actions=["Submit", "Skip"]
        )
    
    # ==================== HELPER METHODS ====================
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract dollar amount from text"""
        match = re.search(r'\$\s*([0-9,]+(?:\.\d{2})?)', text)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                return None
        return None
    
    def _extract_choices(self, text: str) -> List[str]:
        """Extract choices from text"""
        choices = []
        
        # Try numbered list
        numbered = re.findall(r'\d+\.\s+([^\n\r]+)', text)
        if numbered:
            return numbered[:5]  # Max 5 choices
        
        # Try bulleted list
        bulleted = re.findall(r'[•\-\*]\s+([^\n\r]+)', text)
        if bulleted:
            return bulleted[:5]
        
        # Try "X or Y"
        or_choices = re.findall(r'(\w+(?:\s+\w+)*)\s+or\s+(\w+(?:\s+\w+)*)', text, re.I)
        if or_choices:
            return [or_choices[0][0], or_choices[0][1]]
        
        return []