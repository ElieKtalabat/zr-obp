# Copyright (c) Yuta Saito, Yusuke Narita, and ZOZO Technologies, Inc. All rights reserved.
# Licensed under the Apache 2.0 License.

"""Class for Generating Synthetic Logged Bandit Data with Action Embeddings."""
from dataclasses import dataclass
from typing import Callable
from typing import Optional
from typing import Union

import numpy as np
from sklearn.utils import check_scalar

from ..types import BanditFeedback
from ..utils import sample_action_fast
from ..utils import softmax
from .reward_type import RewardType
from .synthetic import linear_reward_function
from .synthetic import logistic_reward_function
from .synthetic import SyntheticBanditDataset


@dataclass
class SyntheticBanditDatasetWithActionEmbeds(SyntheticBanditDataset):
    """Class for synthesizing bandit data with action/item category information or embeddings.

    Note
    -----
    By calling the `obtain_batch_bandit_feedback` method several times,
    we can resample logged bandit data from the same data generating distribution.
    This can be used to estimate confidence intervals of the performances of OPE estimators.

    If `behavior_policy_function`=None, the behavior policy will be generated from the true expected reward function.
    See the description of the `beta` argument, which controls the optimality and entropy of the behavior policy.


    Parameters
    -----------
    n_actions: int
        Number of actions.

    dim_context: int, default=1
        Number of dimensions of context vectors.

    reward_type: str, default='binary'
        Whether the rewards are 'binary' or 'continuous'.
        When 'binary', rewards are sampled from the Bernoulli distribution.
        When 'continuous', rewards are sampled from the truncated Normal distribution with `scale=1`.
        The mean parameter of the reward distribution is determined by the `reward_function` specified by the next argument.

    reward_function: Callable[[np.ndarray, np.ndarray], np.ndarray]], default=None
        Function defining the expected reward for each given action-context pair,
        i.e., :math:`q: \\mathcal{X} \\times \\mathcal{A} \\rightarrow \\mathbb{R}`.
        If None, `obp.dataset.logistic_reward_function` is used when `reward_type='binary'` and
        `obp.dataset.linear_reward_function` is used when `reward_type='continuous'`.

    reward_std: float, default=1.0
        Standard deviation of the reward distribution.
        A larger value leads to a noisier reward distribution.
        This argument is valid only when `reward_type="continuous"`.

    behavior_policy_function: Callable[[np.ndarray, np.ndarray], np.ndarray], default=None
        Function generating logit values, which will be used to define the behavior policy via softmax transformation.
        If None, behavior policy will be generated by applying the softmax function to the expected reward.
        Thus, in this case, it is possible to control the optimality of the behavior policy by customizing `beta`.
        If `beta` is large, the behavior policy becomes near-deterministic/near-optimal,
        while a small or negative value of `beta` leads to a sub-optimal behavior policy.

    beta: int or float, default=1.0
        Inverse temperature parameter, which controls the optimality and entropy of the behavior policy.
        A large value leads to a near-deterministic behavior policy,
        while a small value leads to a near-uniform behavior policy.
        A positive value leads to a near-optimal behavior policy,
        while a negative value leads to a sub-optimal behavior policy.

    n_cat_per_dim: int, default=10
        Number of categories (cardinality) per category dimension.

    latent_param_mat_dim: int, default=5
        Number of dimensions of the latent parameter matrix to define the expected rewards.
        We assume that each category has a corresponding latent parameter representation, which
        affects the expected reward of the category. This parameter matrix is unobserved to the estimators.

    n_cat_dim: int, default=3
        Number of action/item category dimensions.

    p_e_a_param_std: int or float, default=1.0
        Standard deviation of the normal distribution to sample the parameters of the action embedding distribution.
        A large value generates a near-deterministic embedding distribution, while a small value generates a near-uniform embedding distribution.

    n_unobserved_cat_dim: int, default=0
        Number of unobserved category dimensions.
        When there are some unobserved dimensions, the marginalized IPW estimator should have a larger bias.

    n_irrelevant_cat_dim: int, default=0
        Number of category dimensions irrelevant to the expected rewards.
        Discarding irrelevant category dimensions does not increase the bias, while decreasing the variance,
        possibly leading to a better MSE of the resulting estimators.

    n_deficient_actions: int, default=0
        Number of deficient actions having zero probability of being selected in the logged bandit data.
        If there are some deficient actions, the full/common support assumption is very likely to be violated,
        leading to some bias for IPW-type estimators. See Sachdeva et al.(2020) for details.
        `n_deficient_actions` should be an integer smaller than `n_actions - 1` so that there exists at least one action
        that have a positive probability of being selected by the behavior policy.

    random_state: int, default=12345
        Controls the random seed in sampling synthetic bandit data.

    dataset_name: str, default='synthetic_bandit_dataset_with_action_category'
        Name of the dataset.

    Examples
    ----------

    .. code-block:: python

        >>> from obp.dataset import (
            SyntheticBanditDatasetWithActionEmbeds,
            logistic_reward_function
        )

        # generate synthetic contextual bandit feedback with 10 actions and 3 dimensional action embeddings.
        >>> dataset = SyntheticBanditDatasetWithActionEmbeds(
                n_actions=10,
                dim_context=5,
                reward_function=logistic_reward_function,
                beta=5,
                n_cat_per_dim=10,
                n_cat_dim=3,
                random_state=12345,
            )
        >>> bandit_feedback = dataset.obtain_batch_bandit_feedback(n_rounds=100000)
        >>> bandit_feedback

            {
                'n_rounds': 10000,
                'n_actions': 10,
                'action_context': array([[8, 6, 3],
                        [5, 2, 5],
                        [3, 6, 2],
                        [3, 2, 5],
                        [1, 6, 7],
                        [8, 2, 8],
                        [4, 1, 0],
                        [0, 4, 8],
                        [8, 1, 8],
                        [1, 0, 2]]),
                'action_embed': array([[1, 3, 5],
                        [3, 0, 8],
                        [0, 3, 5],
                        ...,
                        [2, 6, 0],
                        [2, 9, 9],
                        [8, 3, 5]]),
                'context': array([[ 0.75820197, -0.5155835 , -0.59120232,  0.89674578, -0.97143752],
                        [ 1.84080991,  0.15388123, -0.27408394, -1.78492569,  0.98100669],
                        [-0.87371714, -1.01563442, -0.41124354,  1.46562117, -1.00621906],
                        ...,
                        [ 1.62370913,  0.34897048, -0.54162779,  0.80960508,  0.62319086],
                        [-0.65634921, -0.72257087, -0.49909509,  0.34077923,  0.16772229],
                        ...,
                        [0.09797275],
                        [0.0740289 ],
                        [0.11308123]]]),
                'pscore': array([0.1194293 , 0.22462219, 0.11744424, ..., 0.0833922 , 0.09694612,
                        0.09797275])
            }


    References
    ------------
    Yuta Saito and Thorsten Joachims.
    "Off-Policy Evaluation for Large Action Spaces via Embeddings." 2022.

    Noveen Sachdeva, Yi Su, and Thorsten Joachims.
    "Off-policy Bandits with Deficient Support." 2020.

    """

    n_actions: int
    dim_context: int = 1
    reward_type: str = RewardType.BINARY.value
    reward_function: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None
    reward_std: Union[int, float] = 1.0
    behavior_policy_function: Optional[
        Callable[[np.ndarray, np.ndarray], np.ndarray]
    ] = None
    beta: Union[int, float] = 0.0
    n_cat_per_dim: int = 10
    latent_param_mat_dim: int = 5
    n_cat_dim: int = 3
    p_e_a_param_std: Union[int, float] = 1.0
    n_unobserved_cat_dim: int = 0
    n_irrelevant_cat_dim: int = 0
    n_deficient_actions: int = 0
    random_state: int = 12345
    dataset_name: str = "synthetic_bandit_dataset_with_action_embed"

    def __post_init__(self) -> None:
        """Initialize Class."""
        super().__post_init__()
        check_scalar(self.n_cat_per_dim, "n_cat_per_dim", int, min_val=1)
        check_scalar(self.latent_param_mat_dim, "latent_param_mat_dim", int, min_val=1)
        check_scalar(self.n_cat_dim, "n_cat_dim", int, min_val=1)
        check_scalar(self.p_e_a_param_std, "p_e_a_param_std", (int, float), min_val=0.0)
        check_scalar(
            self.n_unobserved_cat_dim,
            "n_unobserved_cat_dim",
            int,
            min_val=0,
            max_val=self.n_cat_dim,
        )
        check_scalar(
            self.n_irrelevant_cat_dim,
            "n_irrelevant_cat_dim",
            int,
            min_val=0,
            max_val=self.n_cat_dim,
        )
        self.n_cat_dim += 1
        self.n_unobserved_cat_dim += 1
        self.n_irrelevant_cat_dim += 1
        self._define_action_embed()

        if self.reward_function is None:
            if RewardType(self.reward_type) == RewardType.BINARY:
                self.reward_function = logistic_reward_function
            elif RewardType(self.reward_type) == RewardType.CONTINUOUS:
                self.reward_function = linear_reward_function

    def _define_action_embed(self) -> None:
        """Define action embeddings and latent category parameter matrices."""
        self.latent_cat_param = self.random_.normal(
            size=(self.n_cat_dim, self.n_cat_per_dim, self.latent_param_mat_dim)
        )
        self.p_e_a = softmax(
            self.random_.normal(
                scale=self.p_e_a_param_std,
                size=(self.n_actions, self.n_cat_per_dim, self.n_cat_dim),
            ),
        )
        self.action_context_reg = np.zeros((self.n_actions, self.n_cat_dim), dtype=int)
        for d in np.arange(self.n_cat_dim):
            self.action_context_reg[:, d] = sample_action_fast(
                self.p_e_a[np.arange(self.n_actions, dtype=int), :, d],
                random_state=self.random_state + d,
            )

    def obtain_batch_bandit_feedback(self, n_rounds: int) -> BanditFeedback:
        """Obtain batch logged bandit data.

        Parameters
        ----------
        n_rounds: int
            Data size of the synthetic logged bandit data.

        Returns
        ---------
        bandit_feedback: BanditFeedback
            Synthesized logged bandit data with action category information.

        """
        check_scalar(n_rounds, "n_rounds", int, min_val=1)
        contexts = self.random_.normal(size=(n_rounds, self.dim_context))
        cat_dim_importance = np.zeros(self.n_cat_dim)
        cat_dim_importance[self.n_irrelevant_cat_dim :] = self.random_.dirichlet(
            alpha=self.random_.uniform(size=self.n_cat_dim - self.n_irrelevant_cat_dim),
            size=1,
        )
        cat_dim_importance = cat_dim_importance.reshape((1, 1, self.n_cat_dim))

        # calc expected rewards given context and action (n_data, n_actions)
        q_x_e = np.zeros((n_rounds, self.n_cat_per_dim, self.n_cat_dim))
        q_x_a = np.zeros((n_rounds, self.n_actions, self.n_cat_dim))
        for d in np.arange(self.n_cat_dim):
            q_x_e[:, :, d] = self.reward_function(
                context=contexts,
                action_context=self.latent_cat_param[d],
                random_state=self.random_state + d,
            )
            q_x_a[:, :, d] = q_x_e[:, :, d] @ self.p_e_a[:, :, d].T
        q_x_a = (q_x_a * cat_dim_importance).sum(2)

        # sample actions for each round based on the behavior policy
        if self.behavior_policy_function is None:
            pi_b_logits = q_x_a
        else:
            pi_b_logits = self.behavior_policy_function(
                context=contexts,
                action_context=self.action_context,
                random_state=self.random_state,
            )
        if self.n_deficient_actions > 0:
            pi_b = np.zeros_like(q_x_a)
            n_supported_actions = self.n_actions - self.n_deficient_actions
            supported_actions = np.argsort(
                self.random_.gumbel(size=(n_rounds, self.n_actions)), axis=1
            )[:, ::-1][:, :n_supported_actions]
            supported_actions_idx = (
                np.tile(np.arange(n_rounds), (n_supported_actions, 1)).T,
                supported_actions,
            )
            pi_b[supported_actions_idx] = softmax(
                self.beta * pi_b_logits[supported_actions_idx]
            )
        else:
            pi_b = softmax(self.beta * pi_b_logits)
        actions = sample_action_fast(pi_b, random_state=self.random_state)

        # sample action embeddings based on sampled actions
        action_embed = np.zeros((n_rounds, self.n_cat_dim), dtype=int)
        for d in np.arange(self.n_cat_dim):
            action_embed[:, d] = sample_action_fast(
                self.p_e_a[actions, :, d],
                random_state=d,
            )

        # sample rewards given the context and action embeddings
        expected_rewards_factual = np.zeros(n_rounds)
        for d in np.arange(self.n_cat_dim):
            expected_rewards_factual += (
                cat_dim_importance[0, 0, d]
                * q_x_e[np.arange(n_rounds), action_embed[:, d], d]
            )
        if RewardType(self.reward_type) == RewardType.BINARY:
            rewards = self.random_.binomial(n=1, p=expected_rewards_factual)
        elif RewardType(self.reward_type) == RewardType.CONTINUOUS:
            rewards = self.random_.normal(
                loc=expected_rewards_factual, scale=self.reward_std, size=n_rounds
            )

        return dict(
            n_rounds=n_rounds,
            n_actions=self.n_actions,
            action_context=self.action_context_reg[
                :, 1:
            ],  # action context used for training a reg model
            action_embed=action_embed[
                :, self.n_unobserved_cat_dim :
            ],  # action embeddings used for OPE with MIPW
            context=contexts,
            action=actions,
            position=None,  # position effect is not considered in synthetic data
            reward=rewards,
            expected_reward=q_x_a,
            q_x_e=q_x_e[:, :, self.n_unobserved_cat_dim :],
            p_e_a=self.p_e_a[:, :, self.n_unobserved_cat_dim :],
            pi_b=pi_b[:, :, np.newaxis],
            pscore=pi_b[np.arange(n_rounds), actions],
        )
