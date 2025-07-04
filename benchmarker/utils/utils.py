import time
import numpy as np

# https://stackoverflow.com/a/5998359
current_milli_time = lambda: int(round(time.time() * 1000))

def moving_average(data, window_size):
    weights = np.ones(window_size) / window_size
    return np.convolve(data, weights, mode='same').tolist()
