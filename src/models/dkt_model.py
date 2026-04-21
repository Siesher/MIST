"""
Deep Knowledge Tracing (DKT) Model

Lightweight LSTM-based implementation for knowledge tracing.
Designed to work within 8GB VRAM constraint.

Based on research:
- Deep Knowledge Tracing (Piech et al., 2015)
- DKT-Forget (Nagatani et al., 2019)
- RL-DKT (2025)
"""

import torch
import torch.nn as nn
from typing import List, Dict, Optional, Tuple
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DKTModel(nn.Module):
    """
    Deep Knowledge Tracing using LSTM.

    Input: Sequence of (skill_id, correctness) pairs
    Output: Predicted probability of correct answer for each skill

    Architecture (optimized for 8GB VRAM):
    - Embedding layer for skills
    - Single LSTM layer (hidden_size=64)
    - Output layer for skill predictions
    """

    def __init__(
        self,
        num_skills: int,
        hidden_size: int = 64,
        num_layers: int = 1,
        dropout: float = 0.2,
        embed_size: int = 32
    ):
        """
        Initialize DKT model.

        Args:
            num_skills: Total number of skills/topics
            hidden_size: LSTM hidden layer size (64 for memory efficiency)
            num_layers: Number of LSTM layers (1 recommended)
            dropout: Dropout rate
            embed_size: Skill embedding size
        """
        super().__init__()

        self.num_skills = num_skills
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # Skill embedding: skill_id -> embedding vector
        # Input is skill_id * 2 + correctness (0 or 1)
        self.embedding = nn.Embedding(num_skills * 2, embed_size)

        # LSTM for sequence modeling
        self.lstm = nn.LSTM(
            input_size=embed_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )

        # Output layer: hidden -> skill probabilities
        self.fc = nn.Linear(hidden_size, num_skills)
        self.sigmoid = nn.Sigmoid()

        # Initialize weights
        self._init_weights()

        logger.info(
            f"DKT model initialized: {num_skills} skills, "
            f"hidden_size={hidden_size}, params={self.count_params()}"
        )

    @classmethod
    def from_pretrained(cls, path: str = "data/models/dkt_pretrained.pt", device: str = "cpu") -> "DKTModel":
        """Load a pre-trained DKT model from checkpoint.

        Args:
            path: Path to checkpoint file (.pt)
            device: Device to load model on

        Returns:
            DKTModel with loaded weights
        """
        checkpoint_path = Path(path)
        if not checkpoint_path.exists():
            logger.warning(f"Pre-trained DKT weights not found at {path}, using random init")
            return None

        checkpoint = torch.load(path, map_location=device, weights_only=False)

        # Extract config
        config = checkpoint.get("config", {})
        num_skills = config.get("num_skills", checkpoint.get("num_skills", 123))
        hidden_size = config.get("hidden_size", checkpoint.get("hidden_size", 64))
        num_layers = config.get("num_layers", checkpoint.get("num_layers", 1))
        embed_size = config.get("embed_size", checkpoint.get("embed_size", 32))

        model = cls(
            num_skills=num_skills,
            hidden_size=hidden_size,
            num_layers=num_layers,
            embed_size=embed_size,
        )

        state_dict = checkpoint.get("model_state_dict", checkpoint)
        # Handle key name differences between training and production
        mapped = {}
        for k, v in state_dict.items():
            # Training model uses "output" layer, production uses "fc"
            new_k = k.replace("output.", "fc.") if "output." in k else k
            mapped[new_k] = v

        model.load_state_dict(mapped, strict=False)
        model.to(device)
        model.eval()

        val_auc = config.get("val_auc", checkpoint.get("val_auc", "N/A"))
        logger.info(f"Loaded pre-trained DKT: {num_skills} skills, AUC={val_auc}")

        return model

    def _init_weights(self):
        """Initialize model weights."""
        for name, param in self.named_parameters():
            if 'weight' in name:
                nn.init.xavier_uniform_(param)
            elif 'bias' in name:
                nn.init.zeros_(param)

    def count_params(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def forward(
        self,
        input_ids: torch.Tensor,
        hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass.

        Args:
            input_ids: Tensor of shape (batch, seq_len) with encoded interactions
                       encoded as: skill_id * 2 + correctness
            hidden: Optional initial hidden state (h_0, c_0)

        Returns:
            predictions: Tensor of shape (batch, seq_len, num_skills)
            hidden: Final hidden state (h_n, c_n)
        """
        # Embed interactions
        embedded = self.embedding(input_ids)  # (batch, seq, embed_size)

        # LSTM forward
        if hidden is None:
            lstm_out, hidden = self.lstm(embedded)
        else:
            lstm_out, hidden = self.lstm(embedded, hidden)

        # Predict skill mastery probabilities
        logits = self.fc(lstm_out)  # (batch, seq, num_skills)
        predictions = self.sigmoid(logits)

        return predictions, hidden

    def predict_next(
        self,
        interaction_history: List[Tuple[int, bool]],
        device: str = 'cpu'
    ) -> Dict[int, float]:
        """
        Predict mastery probabilities for all skills given interaction history.

        Args:
            interaction_history: List of (skill_id, correct) tuples
            device: Device to run inference on

        Returns:
            Dictionary mapping skill_id -> predicted probability
        """
        self.eval()

        if not interaction_history:
            # Return uniform prior
            return {i: 0.5 for i in range(self.num_skills)}

        # Encode interactions
        encoded = [
            skill_id * 2 + (1 if correct else 0)
            for skill_id, correct in interaction_history
        ]

        # Convert to tensor
        input_ids = torch.tensor([encoded], dtype=torch.long, device=device)

        with torch.no_grad():
            predictions, _ = self.forward(input_ids)

        # Get last prediction
        last_pred = predictions[0, -1, :].cpu().numpy()

        return {i: float(last_pred[i]) for i in range(self.num_skills)}

    def get_hidden_state(
        self,
        interaction_history: List[Tuple[int, bool]],
        device: str = 'cpu'
    ) -> Optional[List[float]]:
        """
        Get the final hidden state after processing interactions.

        Args:
            interaction_history: List of (skill_id, correct) tuples
            device: Device to run inference on

        Returns:
            Hidden state as list of floats, or None if no history
        """
        if not interaction_history:
            return None

        self.eval()

        # Encode interactions
        encoded = [
            skill_id * 2 + (1 if correct else 0)
            for skill_id, correct in interaction_history
        ]

        input_ids = torch.tensor([encoded], dtype=torch.long, device=device)

        with torch.no_grad():
            _, (h_n, _) = self.forward(input_ids)

        # Return flattened hidden state
        return h_n.squeeze().cpu().tolist()

    def restore_from_hidden(
        self,
        hidden_state: List[float],
        device: str = 'cpu'
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Restore LSTM hidden state from saved values.

        Args:
            hidden_state: Flattened hidden state
            device: Device to create tensors on

        Returns:
            (h_0, c_0) tuple for LSTM continuation
        """
        h_0 = torch.tensor(hidden_state, device=device).view(
            self.num_layers, 1, self.hidden_size
        )
        c_0 = torch.zeros_like(h_0)  # Cell state initialized to zero

        return h_0, c_0


class DKTTrainer:
    """Trainer for DKT model (for future fine-tuning)."""

    def __init__(
        self,
        model: DKTModel,
        learning_rate: float = 0.001,
        device: str = 'cpu'
    ):
        self.model = model.to(device)
        self.device = device
        self.optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        self.criterion = nn.BCELoss()

    def train_step(
        self,
        input_ids: torch.Tensor,
        target_skills: torch.Tensor,
        target_correct: torch.Tensor
    ) -> float:
        """
        Single training step.

        Args:
            input_ids: Encoded interactions (batch, seq_len)
            target_skills: Target skill indices (batch, seq_len)
            target_correct: Target correctness (batch, seq_len)

        Returns:
            Loss value
        """
        self.model.train()
        self.optimizer.zero_grad()

        # Forward pass
        predictions, _ = self.model(input_ids.to(self.device))

        # Get predictions for target skills
        batch_size, seq_len = input_ids.shape
        pred_for_target = predictions.gather(
            2,
            target_skills.unsqueeze(-1).to(self.device)
        ).squeeze(-1)

        # Compute loss
        loss = self.criterion(
            pred_for_target,
            target_correct.float().to(self.device)
        )

        # Backward pass
        loss.backward()
        self.optimizer.step()

        return loss.item()

    def save(self, path: Path):
        """Save model checkpoint."""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'num_skills': self.model.num_skills,
            'hidden_size': self.model.hidden_size,
        }, path)
        logger.info(f"DKT model saved to {path}")

    def load(self, path: Path):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        logger.info(f"DKT model loaded from {path}")


def create_dkt_model(
    num_skills: int = 100,
    hidden_size: int = 64,
    device: str = 'cpu'
) -> DKTModel:
    """
    Factory function to create DKT model.

    Args:
        num_skills: Number of skills to track
        hidden_size: LSTM hidden size (64 recommended for 8GB VRAM)
        device: Device to create model on

    Returns:
        Initialized DKT model
    """
    model = DKTModel(
        num_skills=num_skills,
        hidden_size=hidden_size,
        num_layers=1,  # Keep at 1 for memory efficiency
        dropout=0.2,
        embed_size=32
    )

    return model.to(device)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create model
    model = create_dkt_model(num_skills=50)

    # Simulate interaction history
    history = [
        (0, True),   # Skill 0, correct
        (0, True),   # Skill 0, correct
        (1, False),  # Skill 1, incorrect
        (2, True),   # Skill 2, correct
        (1, True),   # Skill 1, correct (learning!)
    ]

    # Predict mastery
    predictions = model.predict_next(history)

    print("Predicted mastery probabilities:")
    for skill_id, prob in sorted(predictions.items(), key=lambda x: -x[1])[:10]:
        print(f"  Skill {skill_id}: {prob:.3f}")

    # Get hidden state for persistence
    hidden = model.get_hidden_state(history)
    print(f"\nHidden state size: {len(hidden) if hidden else 0}")
