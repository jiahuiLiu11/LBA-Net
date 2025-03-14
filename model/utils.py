import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as f
from torch.nn.parameter import Parameter

class Low_bound(torch.autograd.Function):
    """
    Low_bound makes the numerical calculation close to the bound
    """
    @staticmethod
    def forward(ctx, x, y):
        ctx.save_for_backward(x, y)
        # Ensure all tensors are on the same device
        device = x.device
        y = y.to(device)
        x = torch.clamp(x, min=y)
        return x

    @staticmethod
    def backward(ctx, g):
        x, y = ctx.saved_tensors
        device = x.device
        
        g = g.to(device)
        x = x.to(device)
        y = y.to(device)
        
        grad1 = g.clone()
        grad1[x < y] = 0
        
        pass_through_if = (x >= y) | (g < 0)
        t = pass_through_if.float().to(device)
        
        return grad1 * t, grad1 * t


class GDN(nn.Module):
    def __init__(self, channel_num, inverse=False, gama_init=0.1, beta_min=1e-6, reparam_offset=2**-18):
        super(GDN, self).__init__()

        self.inverse = bool(inverse) # inverse=False
        self.beta_min = float(beta_min)  # beta_min=1e-6
        self.channel_num = int(channel_num) #
        self.gama_init = float(gama_init) # gama_init=0.1
        self.reparam_offset = float(reparam_offset)
        self.pedestal = self.reparam_offset**2
        self.beta_bound = (self.beta_min + self.reparam_offset**2)**0.5
        self.gama_bound = self.reparam_offset

        beta_initializer = torch.sqrt(torch.ones(self.channel_num)+self.pedestal)

        init_matrix = torch.eye(channel_num, channel_num)
        init_matrix = torch.unsqueeze(init_matrix, dim=-1)
        init_matrix = torch.unsqueeze(init_matrix, dim=-1)
        gamma_initializer = torch.sqrt(self.gama_init*init_matrix+self.pedestal)

        self.beta = Parameter(torch.Tensor(channel_num))
        self.beta.data.copy_(beta_initializer)
                                                  
        self.gama = Parameter(torch.Tensor(
            self.channel_num, self.channel_num, 1, 1))
        self.gama.data.copy_(gamma_initializer)

    def forward(self, x):
        gama = Low_bound.apply(self.gama, torch.tensor(self.gama_bound).cuda())

        gama = gama ** 2 - self.pedestal
        beta = Low_bound.apply(self.beta, torch.tensor(self.beta_bound).cuda())

        beta = beta ** 2 - self.pedestal

        norm_pool = f.conv2d(x ** 2.0, weight=gama, bias=beta)
        if self.inverse:
            norm_pool = torch.sqrt(norm_pool)
        else:
            norm_pool = torch.rsqrt(norm_pool)

        return x * norm_pool
    
def conv(in_channels, out_channels, kernel_size=5, stride=2):
    return nn.Conv2d(
        in_channels,
        out_channels,
        kernel_size=kernel_size,
        stride=stride,
        padding=kernel_size // 2,
    )


def deconv(in_channels, out_channels, kernel_size=5, stride=2):
    return nn.ConvTranspose2d(
        in_channels,
        out_channels,
        kernel_size=kernel_size,
        stride=stride,
        output_padding=stride - 1,
        padding=kernel_size // 2,
    )
