import tempfile
import unittest
from pathlib import Path
import torch
from safetensors.torch import save_file
from native_models import load_checkpoint


class ComplexBufferModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight=torch.nn.Parameter(torch.zeros(2))
        self.register_buffer('rotary',torch.zeros(2,dtype=torch.complex64))


class CheckpointTests(unittest.TestCase):
    def test_pixal_complex_rotary_buffers_load_without_losing_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'weights.safetensors'
            rotary=torch.tensor([1+2j,3-4j],dtype=torch.complex64)
            save_file({'weight':torch.tensor([5.,6.]),'rotary':rotary},path)
            model=load_checkpoint(ComplexBufferModel,str(path),{})
            self.assertTrue(torch.equal(model.rotary,rotary))
            self.assertTrue(torch.equal(model.weight,torch.tensor([5.,6.])))
