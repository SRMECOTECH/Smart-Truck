"""
Standalone training runner.

Usage:
    cd backend/app
    python -m ml.run_training
"""

import sys
from pathlib import Path

# Ensure app directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .train import run_training

if __name__ == "__main__":
    metadata = run_training()
    print("\n\nTraining Summary:")
    print(f"  Samples used: {metadata['training_samples']}")
    print(f"  R2 Score:     {metadata['metrics']['r2_score']}")
    print(f"  MAE:          {metadata['metrics']['mae_hours']} hours")
    print(f"  MAPE:         {metadata['metrics']['mape_percent']}%")
    print(f"  Within 20%:   {metadata['metrics']['within_20_pct_accuracy']}%")
    print(f"\nModel saved to: ml/models/eta_model.pkl")
