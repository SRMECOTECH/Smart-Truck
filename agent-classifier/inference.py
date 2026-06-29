"""
Agent Classifier — Production Inference
========================================
Load the trained model and classify user queries into agent classes.
Use this in your LangGraph chatboard for routing.

Usage:
    classifier = AgentClassifier("agent_classifier_export")
    result = classifier.predict("predict ETA from Raipur to Nagpur")
    print(result)
    # {
    #   'agent': 'eta_sla_prediction',
    #   'confidence': 0.94,
    #   'action': 'route',
    #   'all_scores': {...},
    #   'entities': {'has_route_pair': True, 'has_predict_intent': True, ...}
    # }
"""

import json
import re
import numpy as np
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel


# ── Entity Feature Extraction (must match training) ──────────────────────────

VEHICLE_RE = re.compile(r'[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}', re.IGNORECASE)
DRIVER_ID_RE = re.compile(r'\bdriver\s+\d+\b', re.IGNORECASE)
TRIP_ID_RE = re.compile(r'\btrip\s+\d+\b', re.IGNORECASE)
DATE_RE = re.compile(
    r'\d{4}-\d{2}-\d{2}'
    r'|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b'
    r'|\b(?:last|this|past|next)\s+(?:week|month|quarter|year)\b'
    r'|\b(?:today|yesterday|tomorrow|kal|aaj)\b'
    r'|\b(?:last|past)\s+\d+\s+days\b',
    re.IGNORECASE
)
ROUTE_RE = re.compile(r'\bfrom\s+\w+\s+to\s+\w+|\w+\s+to\s+\w+\s+route|\w+\s+se\s+\w+', re.IGNORECASE)


def extract_aux_features(text):
    """Extract 14 auxiliary features from query text."""
    t = text.lower()
    return [
        1.0 if VEHICLE_RE.search(text) else 0.0,
        1.0 if DRIVER_ID_RE.search(text) else 0.0,
        1.0 if TRIP_ID_RE.search(text) else 0.0,
        1.0 if DATE_RE.search(text) else 0.0,
        1.0 if ROUTE_RE.search(text) else 0.0,
        1.0 if any(w in t for w in ['predict', 'forecast', 'estimate', 'expected', 'will it', 'probability', 'how long will']) else 0.0,
        1.0 if any(w in t for w in ['optimize', 'best route', 'recommend', 'suggest', 'optimal', 'alternative', 'assign']) else 0.0,
        1.0 if any(w in t for w in ['alert', 'anomaly', 'unusual', 'suspicious', 'outlier', 'warning', 'scan', 'flag']) else 0.0,
        1.0 if any(w in t for w in ['fatigue', 'tired', 'rest', 'safety', 'workload', 'consecutive days', 'hours driving', 'overwork']) else 0.0,
        1.0 if any(w in t for w in ['fleet', 'dashboard', 'overall', 'kpi', 'fleet-wide']) else 0.0,
        1.0 if any(w in t for w in ['demand', 'volume', 'growth', 'seasonal', 'client forecast', 'next week', 'client profile']) else 0.0,
        1.0 if any(w in t for w in ['vehicle', 'asset', 'truck']) else 0.0,
        min(len(text) / 100.0, 1.0),
        min(len(text.split()) / 20.0, 1.0),
    ]


def extract_entities(text):
    """Extract named entities for downstream agent use."""
    entities = {}

    vehicle = VEHICLE_RE.search(text)
    if vehicle:
        entities['vehicle_id'] = vehicle.group()

    driver_id = re.search(r'\bdriver\s+(\d+)\b', text, re.IGNORECASE)
    if driver_id:
        entities['driver_id'] = int(driver_id.group(1))

    trip_id = re.search(r'\btrip\s+(\d+)\b', text, re.IGNORECASE)
    if trip_id:
        entities['trip_id'] = int(trip_id.group(1))

    route_match = re.search(r'from\s+(\w+)\s+to\s+(\w+)', text, re.IGNORECASE)
    if route_match:
        entities['origin'] = route_match.group(1)
        entities['destination'] = route_match.group(2)
    else:
        route_match2 = re.search(r'(\w+)\s+to\s+(\w+)\s+route', text, re.IGNORECASE)
        if route_match2:
            entities['origin'] = route_match2.group(1)
            entities['destination'] = route_match2.group(2)

    date = DATE_RE.search(text)
    if date:
        entities['date_expr'] = date.group()

    return entities


# ── Model Architecture (must match training) ─────────────────────────────────

class AgentClassifierModel(nn.Module):
    def __init__(self, model_name, num_classes, aux_dim, dropout=0.3):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        hidden = self.encoder.config.hidden_size

        self.drop = nn.Dropout(dropout)
        combined = hidden + aux_dim

        self.head = nn.Sequential(
            nn.Linear(combined, 256),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128, num_classes)
        )

    def forward(self, input_ids, attention_mask, aux):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        tokens = out.last_hidden_state
        mask = attention_mask.unsqueeze(-1).float()
        pooled = (tokens * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        pooled = self.drop(pooled)
        combined = torch.cat([pooled, aux], dim=1)
        return self.head(combined)


# ── Main Classifier Class ────────────────────────────────────────────────────

class AgentClassifier:
    """
    Production agent classifier.

    Args:
        model_dir: Path to exported model directory (from Colab training).
        device: 'cuda', 'cpu', or 'auto'.
    """

    def __init__(self, model_dir, device='auto'):
        # Load config
        with open(f'{model_dir}/config.json', 'r') as f:
            self.config = json.load(f)

        # Device
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        # Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.max_len = self.config['max_len']

        # Label map
        self.class_names = self.config['class_names']
        self.label_map = {int(k): v for k, v in self.config['label_map'].items()}
        self.thresholds = self.config['confidence_thresholds']

        # Model
        self.model = AgentClassifierModel(
            model_name=self.config['model_name'],
            num_classes=self.config['num_classes'],
            aux_dim=self.config['aux_dim'],
            dropout=self.config.get('dropout', 0.3)
        )
        state_dict = torch.load(
            f'{model_dir}/model.pt',
            map_location=self.device,
            weights_only=True
        )
        self.model.load_state_dict(state_dict)
        self.model.to(self.device)
        self.model.eval()

    def predict(self, query, top_k=3):
        """
        Classify a query into an agent.

        Returns:
            dict with keys:
                agent: str — predicted agent name
                confidence: float — probability of top prediction
                action: str — 'route' | 'route_monitor' | 'clarify' | 'multi_agent'
                top_k: list of (agent_name, probability) tuples
                entities: dict — extracted entities from query
        """
        # Tokenize
        enc = self.tokenizer(
            query,
            max_length=self.max_len,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        ids = enc['input_ids'].to(self.device)
        mask = enc['attention_mask'].to(self.device)

        # Aux features
        aux = torch.tensor(
            [extract_aux_features(query)],
            dtype=torch.float32
        ).to(self.device)

        # Inference
        with torch.no_grad():
            logits = self.model(ids, mask, aux)
            probs = torch.softmax(logits.float(), dim=1)[0]

        # Top-k
        top_probs, top_indices = probs.topk(min(top_k, len(self.class_names)))
        top_results = [
            (self.label_map[idx.item()], prob.item())
            for idx, prob in zip(top_indices, top_probs)
        ]

        confidence = top_results[0][1]
        agent = top_results[0][0]

        # Determine action
        if len(top_results) >= 2 and (top_results[0][1] - top_results[1][1]) < 0.15:
            action = 'multi_agent'
        elif confidence >= self.thresholds['high']:
            action = 'route'
        elif confidence >= self.thresholds['medium']:
            action = 'route_monitor'
        else:
            action = 'clarify'

        # Extract entities for downstream use
        entities = extract_entities(query)

        return {
            'agent': agent,
            'confidence': round(confidence, 4),
            'action': action,
            'top_k': top_results,
            'entities': entities,
        }

    def batch_predict(self, queries, top_k=1):
        """Predict for a list of queries."""
        return [self.predict(q, top_k=top_k) for q in queries]


# ── CLI demo ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    model_dir = sys.argv[1] if len(sys.argv) > 1 else 'agent_classifier_export'
    classifier = AgentClassifier(model_dir)

    test_queries = [
        "show me fleet summary",
        "Rajesh Kumar ka performance kaisa hai",
        "predict ETA from Raipur to Nagpur",
        "scan last 7 days for anomalies",
        "is driver 4521 safe to dispatch",
        "best route from Mumbai to Pune",
        "vehicle CG04MC9150 ki details",
        "demand forecast for Delhi to Jaipur",
        "show trip 45892 details",
        "Raipur to Nagpur route performance",
    ]

    for q in test_queries:
        result = classifier.predict(q, top_k=3)
        print(f"\nQuery: \"{q}\"")
        print(f"  Agent: {result['agent']} ({result['confidence']:.1%})")
        print(f"  Action: {result['action']}")
        if result['entities']:
            print(f"  Entities: {result['entities']}")
        for name, prob in result['top_k']:
            bar = '#' * int(prob * 30)
            print(f"    {name:<25s} {prob:>6.1%} {bar}")
