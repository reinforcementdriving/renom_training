# encoding:utf-8
import renom as rm
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from pdb import set_trace
from numpy import random
from time import time
from skimage import io
from glob import glob
import gzip
from vae_func import VGG_Enc, Dec, Vae2d, keras_Enc, keras_Dec, Densenet_Enc
from renom.cuda.cuda import set_cuda_active
from numpy.random import seed, permutation


def load(fname, shape, offset):
    with gzip.open(fname, 'rb') as f:
        data = np.frombuffer(f.read(), np.uint8, offset=offset).reshape(shape)
    return data

if 0:
    fls = glob('mnist/*.gz')
    data = [[[],[]], [[],[]]]
    for fname in fls:
        shapes = [(-1, 1), (-1, 1, 28, 28)]
        offsets = (8, 16)
        type_idx = 0 if 'labels' in fname else 1
        idx = 0 if 'train' in fname else 1
        data[idx][type_idx] = load(fname, shapes[type_idx], offsets[type_idx])
    data = np.array(data)
    np.save('mnist/data.npy', data)
else:
    data = np.load('mnist/data.npy')

y_train = data[0][0]
x_train = data[0][1].astype('float32')/255.
y_test = data[1][0]
x_test = data[1][1].astype('float32')/255.

set_cuda_active(True)
seed(10)

latent_dim = 2
epoch = 10 
batch_size = 256

model = 'densenet'

if model == 'vgg':
    enc = VGG_Enc(
        latent_dim = latent_dim,
        max_channels=64, 
        intermidiate_dim = 16,
        depth=4,
        batch_normal=True)
elif model == 'densenet':
    enc = Densenet_Enc(
        initial_channel=4,
        growth_rate=4,
        latent_dim=latent_dim,
        blocks=3,
        )
else:
    enc = keras_Enc()
if 1:
    dec = Dec()
else:
    dec = keras_Dec()

vae = Vae2d(enc, dec)

optimizer = rm.Adam()

N = len(x_train)
curve = []
for e in range(epoch):
    perm = permutation(N)
    batch_loss = []
    for offset in range(0, N, batch_size):
        idx = perm[offset: offset+batch_size]
        s = time()
        with vae.train():
            ft = time()
            l = vae(x_train[idx])
            bt = time()
            ft = bt - ft
            grad = l.grad()
            bt = time() - bt
        s = time() - s
        grad.update(optimizer)
        batch_loss.append([
            vae.kl_loss.as_ndarray()[0], 
            vae.recon_loss.as_ndarray(), ft, bt, s])
        loss_na = np.array(batch_loss)
        kl_loss = loss_na[:,0].mean()
        recon_loss = loss_na[:,1].mean()
        ft_mean = loss_na[:,-3].mean()
        bt_mean = loss_na[:,-2].mean()
        s_mean = loss_na[:,-1].mean()
        print('{}/{} KL:{:.3f} ReconE:{:.3f} ETA:{:.1f}sec / {:.2f}-{:.2f}'.format(
            offset, N, kl_loss, recon_loss, (N-offset)/batch_size*s_mean, ft_mean, bt_mean),
            flush=True, end='\r')
    curve.append([kl_loss, recon_loss])
    print('#{} KL:{:.3f} ReconE:{:.3f} @ {:.1f}sec {:>10}'.format(
        e, kl_loss, recon_loss, loss_na[:,2].sum(), ''))

    if latent_dim == 2:
        res, _ = enc(x_test[:batch_size])
        res = res.as_ndarray()
        for i in range(batch_size, len(x_test), batch_size):
            z_mean, _ = enc(x_test[i:i+batch_size])
            res = np.r_[res, z_mean.as_ndarray()]
        plt.clf()
        plt.scatter(res[:,0], res[:,1], c=y_test.reshape(-1,))
        plt.savefig('result/{}_latent{}.png'.format(model, e))

        z_mean, _ = enc(x_train[perm[:batch_size]])
        z_mean = z_mean.as_ndarray()
        lft, rgt = z_mean[:,0].min(), z_mean[:,0].max()
        lwr, upr = z_mean[:,1].min(), z_mean[:,1].max()
        # 16 x 16 = 256
        res_dim = 16
        cv = np.zeros((res_dim*28, res_dim*28))
        h = np.linspace(lft, rgt, res_dim)
        v = np.linspace(lwr, upr, res_dim)
        data = []
        for i in range(res_dim):
            for j in range(res_dim):
                data.append(
                    np.array([h[i],v[j]])
                )
        data = np.array(data).astype('float32')
        res = dec(data).as_ndarray()
        for i in range(res_dim):
            for j in range(res_dim):
                cv[i*28:(i+1)*28, j*28:(j+1)*28] = res[
                    i*res_dim + j
                ].reshape(28, 28)
        cv *= 255
        cv = cv.astype('uint8')
        io.imsave('result/{}_decode{}.png'.format(model, e), cv)