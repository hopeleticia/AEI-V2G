"""
scheduling/replay_buffer.py
============================
Sequence replay buffer for DRQN (Deep Recurrent Q-Network) training.

Why sequences, not individual transitions?
------------------------------------------
Standard DQN samples individual (s, a, r, s') tuples.  DRQN needs the LSTM
to see *temporal context* — it must read a sequence of states to build up
its hidden representation.  We therefore store complete episode trajectories
and sample fixed-length subsequences (burn-in + target window) from them.

This mirrors the sampling strategy from the IBTD anchor paper (Zhao et al.,
IET Comms 2024) adapted for the V2G energy dispatch domain.

Burn-in:
    The first BURN_IN steps of each sampled sequence are used only to warm
    up the LSTM hidden state (gradients are not backpropagated through them).
    The remaining SEQ_LEN - BURN_IN steps are used for the TD loss.

Research objective mapping
--------------------------
  Obj-8  DRQN training infrastructure (sequence buffer enables BPTT).
"""
from __future__ import annotations

import random
from collections import deque
from typing import NamedTuple


class Step(NamedTuple):
    """One time step within an episode trajectory."""
    state: list[float]
    action: int
    reward: float
    next_state: list[float]
    done: bool


class SequenceReplayBuffer:
    """Stores complete episode trajectories; samples fixed-length subsequences.

    Parameters
    ----------
    capacity  : maximum number of *episodes* to retain.
    seq_len   : length of subsequences sampled for training.
    burn_in   : number of leading steps used only for LSTM warm-up (no loss).
    """

    def __init__(self, capacity: int = 500, seq_len: int = 8, burn_in: int = 4) -> None:
        if burn_in >= seq_len:
            raise ValueError("burn_in must be less than seq_len")
        self.capacity = capacity
        self.seq_len = seq_len
        self.burn_in = burn_in
        self._episodes: deque[list[Step]] = deque(maxlen=capacity)
        self._current_episode: list[Step] = []

    # ── Episode construction ──────────────────────────────────────────────────

    def push(self, state: list[float], action: int, reward: float,
             next_state: list[float], done: bool) -> None:
        """Append one step to the current (open) episode."""
        self._current_episode.append(Step(state, action, reward, next_state, done))
        if done:
            self.close_episode()

    def close_episode(self) -> None:
        """Finalise the current episode and add it to storage.

        Called explicitly at episode end (done=True) or from reset_episode()
        if the episode ended without a terminal signal.
        """
        if self._current_episode:
            self._episodes.append(list(self._current_episode))
            self._current_episode = []

    def reset_episode(self) -> None:
        """Discard any partially-built episode and start fresh."""
        self._current_episode = []

    # ── Sampling ─────────────────────────────────────────────────────────────

    def sample(self, batch_size: int) -> list[list[Step]] | None:
        """Return *batch_size* random subsequences each of length *seq_len*.

        Returns None if there are not yet enough stored episodes.  The
        minimum threshold is 1 episode longer than seq_len so that at least
        one full subsequence can be extracted.
        """
        eligible = [ep for ep in self._episodes if len(ep) >= self.seq_len]
        if len(eligible) < max(1, batch_size // 4):
            return None
        batch: list[list[Step]] = []
        for _ in range(batch_size):
            episode = random.choice(eligible)
            max_start = len(episode) - self.seq_len
            start = random.randint(0, max_start)
            batch.append(episode[start : start + self.seq_len])
        return batch

    def __len__(self) -> int:
        """Total number of stored *episodes* (not steps)."""
        return len(self._episodes)

    @property
    def total_steps(self) -> int:
        """Total number of steps across all stored episodes."""
        return sum(len(ep) for ep in self._episodes) + len(self._current_episode)

    def can_train(self, min_episodes: int = 4) -> bool:
        """True when enough complete episodes exist to start training."""
        eligible = [ep for ep in self._episodes if len(ep) >= self.seq_len]
        return len(eligible) >= min_episodes
