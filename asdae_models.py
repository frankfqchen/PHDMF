'''
Created on July 21, 2017

@author: Beili
'''

import os
import time

from util import eval_RMSE
import math
import numpy as np
from text_analysis.models import CNN_module
from text_analysis.aSDAE import aSDAE_module


def PHDMF(res_dir, train_user, train_item, valid_user, test_user,
           R, CNN_X, aSDAE, vocab_size, init_W=None, give_item_weight=True,
           max_iter=50, lambda_u=1, lambda_v=100, dimension=50,
           dropout_rate=0.2, emb_dim=200, max_len=300, num_kernel_per_ws=100):
    # explicit setting
    a = 1
    b = 0
    aSDAE_encoder_dimension=100
    user_feature=42
 
    num_user = R.shape[0]
    num_item = R.shape[1]
    PREV_LOSS = 1e-50
    if not os.path.exists(res_dir):
        os.makedirs(res_dir)
    f1 = open(res_dir + '/state.log', 'w')

    Train_R_I = train_user[1]
    Train_R_J = train_item[1]
    Test_R = test_user[1]
    Valid_R = valid_user[1]

    if give_item_weight is True:
        item_weight = np.array([math.sqrt(len(i))
                                for i in Train_R_J], dtype=float)
        item_weight = (float(num_item) / item_weight.sum()) * item_weight
    else:
        item_weight = np.ones(num_item, dtype=float)

    pre_val_eval = 1e10

    #cnn_module = CNN_module(dimension, vocab_size, dropout_rate,emb_dim, max_len, num_kernel_per_ws, init_W)
    #theta = cnn_module.get_projection_layer(CNN_X)
    asdae_module = aSDAE_module(aSDAE_encoder_dimension,dimension,num_item,user_feature)

    alpha = asdae_module.get_middle_layer(R.toarray(),aSDAE.toarray())  
    np.random.seed(133)
    V = np.random.uniform(size=(num_item, dimension))
    U = alpha
    #V = theta

    endure_count = 5
    count = 0
    for iteration in xrange(max_iter):
        loss = 0
        tic = time.time()
        print "%d iteration\t(patience: %d)" % (iteration, count)

        VV = b * (V.T.dot(V)) + lambda_u * np.eye(dimension)
        #sub_loss = np.zeros(num_user)

        for i in xrange(num_user):
            idx_item = train_user[0][i]
            V_i = V[idx_item]
            R_i = Train_R_I[i]
            A = VV + (a - b) * (V_i.T.dot(V_i))
            B = (a * V_i * (np.tile(R_i, (dimension, 1)).T)).sum(0) + lambda_u * alpha[i]

            U[i] = np.linalg.solve(A, B)

            #sub_loss[i] = -0.5 * lambda_u * np.dot(U[i], U[i])

        #loss = loss + np.sum(sub_loss)
        asdae_seed = np.random.randint(100000)
        asdae_history = asdae_module.train(R.toarray(),aSDAE.toarray(),U,asdae_seed)
        alpha = asdae_module.get_middle_layer(R.toarray(),aSDAE.toarray())
        loss = loss - 0.5 * lambda_u * asdae_history.history['loss'][-1]

        sub_loss = np.zeros(num_item)
        UU = b * (U.T.dot(U))
        for j in xrange(num_item):
            idx_user = train_item[0][j]
            U_j = U[idx_user]
            R_j = Train_R_J[j]

            tmp_A = UU + (a - b) * (U_j.T.dot(U_j))
            A = tmp_A + lambda_v * item_weight[j] * np.eye(dimension)
            B = (a * U_j * (np.tile(R_j, (dimension, 1)).T)
                 ).sum(0)
            V[j] = np.linalg.solve(A, B)
            
            sub_loss[j] = -0.5 * lambda_v * np.dot(V[j],V[j])        
            sub_loss[j] = sub_loss[j] + -0.5 * np.square(R_j * a).sum()
            sub_loss[j] = sub_loss[j] + a * np.sum((U_j.dot(V[j])) * R_j)
            sub_loss[j] = sub_loss[j] - 0.5 * np.dot(V[j].dot(tmp_A), V[j])

        loss = loss + np.sum(sub_loss)
        #seed = np.random.randint(100000)
        #history = cnn_module.train(CNN_X, V, item_weight, seed)
        #theta = cnn_module.get_projection_layer(CNN_X)
        #cnn_loss = history.history['loss'][-1]

        #loss = loss - 0.5 * lambda_v * cnn_loss * num_item

        tr_eval = eval_RMSE(Train_R_I, U, V, train_user[0])
        val_eval = eval_RMSE(Valid_R, U, V, valid_user[0])
        te_eval = eval_RMSE(Test_R, U, V, test_user[0])

        toc = time.time()
        elapsed = toc - tic

        converge = abs((loss - PREV_LOSS) / PREV_LOSS)

        if (val_eval < pre_val_eval):
            asdae_module.save_model(res_dir + '/aSDAE_weights.hdf5')
            np.savetxt(res_dir + '/U.dat', U)
            np.savetxt(res_dir + '/V.dat', V)
            #np.savetxt(res_dir + '/theta.dat', theta)
            np.savetxt(res_dir + '/alpha.dat', alpha)
        else:
            count = count + 1

        pre_val_eval = val_eval

        print "Loss: %.5f Elpased: %.4fs Converge: %.6f Tr: %.5f Val: %.5f Te: %.5f" % (
            loss, elapsed, converge, tr_eval, val_eval, te_eval)
        f1.write("Loss: %.5f Elpased: %.4fs Converge: %.6f Tr: %.5f Val: %.5f Te: %.5f\n" % (
            loss, elapsed, converge, tr_eval, val_eval, te_eval))

        if (count == endure_count):
            break

        PREV_LOSS = loss

    f1.close()
