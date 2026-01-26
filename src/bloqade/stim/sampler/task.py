from typing import ClassVar

from bloqade.stim.sampler.base import SamplingTaskBase


class SamplingTask(SamplingTaskBase):

    _supports_batch_size: ClassVar[bool] = False
