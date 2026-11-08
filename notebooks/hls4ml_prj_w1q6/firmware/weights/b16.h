//Numpy array shape [32]
//Min 0.000000000000
//Max 0.000000000000
//Number of zeros 32

#ifndef B16_H_
#define B16_H_

#ifndef __SYNTHESIS__
bias16_t b16[32];
#else
bias16_t b16[32] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

#endif

#endif
