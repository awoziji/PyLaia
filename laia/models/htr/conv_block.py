import torch
import torch.nn as nn

from collections import OrderedDict
from laia.data import PaddedTensor

class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=3, dilation=1,
                 activation=nn.LeakyReLU, poolsize=None, dropout=0.0,
                 batchnorm=False, inplace=False):
        super(ConvBlock, self).__init__()
        assert (not dropout or dropout < 1.0), (
            'Dropout rate must be lower than 1.0')
        if not isinstance(kernel_size, (list, tuple)):
            kernel_size = (kernel_size, kernel_size)
        if not isinstance(dilation, (list, tuple)):
            dilation = (dilation, dilation)
        if poolsize and not isinstance(poolsize, (list, tuple)):
            poolsize = (poolsize, poolsize)

        # This is a torch tensor used to divide the input sizes in the forward()
        # method, when using a PaddedTensor as an input.
        # If no padding is effectively used, then this is set to None.
        self._poolsize = (torch.LongTensor(poolsize)
                          if poolsize and poolsize[0] > 0 and poolsize[1] > 0
                          and (poolsize[0] > 1 or poolsize[1] > 1)
                          else None)

        # First, add dropout module (optionally)
        if dropout and dropout > 0.0:
            self.add_module('dropout', nn.Dropout(dropout, inplace=inplace))

        # Add Conv2d layer (compute padding to perform a full convolution).
        padding = ((kernel_size[0] - 1) // 2 * dilation[0],
                   (kernel_size[1] - 1) // 2 * dilation[1])
        self.add_module('conv',
                        nn.Conv2d(in_channels, out_channels, kernel_size,
                                  padding=padding, dilation=dilation))

        # Add Batch normalization
        if batchnorm:
            self.add_module('batchnorm', nn.BatchNorm2d(out_channels))

        if inplace:
            # Activation function must support inplace operations.
            self.add_module('activation', activation(inplace=True))
        else:
            self.add_module('activation', activation())

        # Add maxpool layer
        if self._poolsize is not None:
            self.add_module('pooling', nn.MaxPool2d(poolsize))

    def forward(self, x):
        is_padded = isinstance(x, PaddedTensor)
        if is_padded:
            xs = x.sizes
            x = x.data
            assert xs.dim() == 2, 'PaddedTensor.sizes must be a matrix'
            assert xs.size(1) == 2, (
                'PaddedTensor.sizes must have 2 colums: Height and Width, '
                '%d columns given instead.' % xs.size(1))
        # Forward the input through all the modules in the conv block
        for module in self._modules.values():
            x = module(x)
        if is_padded:
            if self._poolsize is not None:
                xs = xs / self._poolsize
            return PaddedTensor(data=x, sizes=xs)
        else:
            return x

    def cpu(self):
        super(ConvBlock, self).cpu()
        if self._poolsize is not None:
            self._poolsize = self._poolsize.cpu()
        return self

    def cuda(self):
        super(ConvBlock, self).cuda()
        if self._poolsize is not None:
            self._poolsize = self._poolsize.cuda()
        return self
