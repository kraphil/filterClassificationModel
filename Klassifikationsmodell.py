
import importlib
import argparse
import os, sys
import argparse
import pandas as pd
import numpy as np
import pickle
import time
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_curve, auc, precision_recall_curve

from torch.autograd import Variable

import keras
from keras import backend as K
from keras.models import Sequential, Model
from keras.layers import Input, LSTM, RepeatVector, Bidirectional, Reshape, TimeDistributed, concatenate, Flatten, Activation, Dot, BatchNormalization
from keras.layers.core import Flatten, Dense, Dropout, Lambda
from keras.optimizers import SGD, RMSprop, Adam
from keras.callbacks import ModelCheckpoint, TensorBoard
from keras import objectives
from keras.utils.vis_utils import plot_model

sys.path.insert(0, 'utils.py')
sys.path.insert(0, 'models.py')
from utils import *
from models import *

name = 'small_log'
#name = 'large_log'
#name = 'bpic_2012'
#name = 'bpic_2013'
 
"""
parser = {
    'train': True,
    'test': True,
    #'model_class': 'AE',
    'model_name': '',
    'data_dir': '../data/',
    'data_file': name + '.csv',
    'anomaly_pct': 0.1,
    #'input_dir': '../input/{}/'.format(name), 
    'output_dir': './output/{}/'.format(name),
    'scaler': 'standardization',
    'batch_size' : 16,
    'epochs' : 10,
    'no_cuda' : False,
    'seed' : 7,
    'layer1': 1000,
    'layer2': 100,
    'lr': 0.002,
    'betas': (0.9, 0.999),   
    'lr_decay': 0.90,
}
"""

#args = argparse.Namespace(**parser)

preprocessed_data_name = os.path.join('preprocessed_data_{}.pkl'.format(args.anomaly_pct))
with open(preprocessed_data_name, 'rb') as f:
    input_train = pickle.load(f)
    input_val = pickle.load(f)
    input_test = pickle.load(f)
    pad_index_train = pickle.load(f)
    pad_index_val = pickle.load(f)
    pad_index_test = pickle.load(f)
    activity_label_test = pickle.load(f)
    activity_label_val = pickle.load(f)
    time_label_val = pickle.load(f)
    time_label_test = pickle.load(f)
    train_case_num = pickle.load(f)
    val_case_num = pickle.load(f)
    test_case_num = pickle.load(f)
    train_row_num = pickle.load(f)
    val_row_num = pickle.load(f)
    test_row_num = pickle.load(f)
    min_value = pickle.load(f)
    max_value = pickle.load(f)
    mean_value = pickle.load(f)
    std_value = pickle.load(f)
    cols = pickle.load(f)
    statistics_storage = pickle.load(f)
    true_time = pickle.load(f)
    true_act = pickle.load(f)
    full_true_time = pickle.load(f)
    full_true_act = pickle.load(f)

#df
normal_df_name = os.path.join('normal_df_{}.csv'.format(args.anomaly_pct))
normal_df = pd.read_csv(normal_df_name)

anomalous_df_name = os.path.join('anomolous_df_{}.csv'.format(args.anomaly_pct))
anomalous_df = pd.read_csv(anomalous_df_name)

#test
caseid_test = normal_df['CaseID'][-test_row_num:]
normal_df_test = normal_df[-test_row_num:]
anomalous_df_test = anomalous_df[-test_row_num:]

data_df = pd.DataFrame({'ActivityLabel': activity_label_test,
                              'TimeLabel': time_label_test})
data_df.head()

input_train.shape

"""Modell"""

#Variablen
timesteps = input_train.shape[1]
input_dim = input_train.shape[2]
latent_dim = 100 
z_dim =2
epsilon_std=1

#Input
inputs = Input(shape=(timesteps, input_dim))

#Encoder Bidirectional LSTM
encoder_stack_h, encoder_last_h, encoder_last_c, *_ = Bidirectional(LSTM(latent_dim, activation="relu", return_state=True, return_sequences=True, dropout = 0.5))(inputs)
encoder_last_h = BatchNormalization(momentum=0.6)(encoder_last_h)
encoder_last_c = BatchNormalization(momentum=0.6)(encoder_last_c)
print(encoder_stack_h)
print(encoder_last_h)

#Variational Layer
z_mean = Dense(z_dim)(encoder_stack_h)
print(z_mean)
z_log_sigma = Dense(z_dim)(encoder_stack_h)
print(z_log_sigma)

def sampling(args):
        z_mean, z_log_sigma = args
        epsilon = K.random_normal(shape=(K.shape(z_mean)[0],z_dim),
                                  mean=0., stddev=epsilon_std)
        return z_mean + z_log_sigma * epsilon

z = Lambda(sampling)([z_mean, z_log_sigma])

#Decoder Bidirectional LSTM
decoder = RepeatVector(timesteps)(encoder_last_h)
decoder = Bidirectional(LSTM(latent_dim, activation="relu", return_sequences=True, dropout = 0.5))(decoder)
print(decoder)

#Self-Attention Layer
attention = keras.layers.dot([decoder, z], axes=[1,1])
attention = Activation('softmax')(attention)
print(attention))

context = keras.layers.dot([z, attention], axes=[2,2])
print(context)
decoder_combined_context = concatenate([context, decoder])

#Output
output = TimeDistributed(Dense(input_dim, activation='sigmoid'))(decoder_combined_context)
lstmae = Model(inputs, output)

#Loss Function
def vae_loss(inputs, decoder_combined_context):
        xent_loss = objectives.mse(inputs, decoder_combined_context)
        kl_loss = - 0.5 * K.mean(1 + z_log_sigma - K.square(z_mean) - K.exp(z_log_sigma))
        loss = xent_loss + kl_loss
        return loss

#Modell bauen
lstmae.compile(optimizer=Adam(learning_rate=0.006), loss=vae_loss)
lstmae.summary()
plot_model(lstmae, to_file='model_plot.png', show_shapes=True, show_layer_names=True)

checkpointer = ModelCheckpoint(filepath="model_seqs2.h5",
                              verbose=0,
                              save_best_only=True)

tensorboard = TensorBoard(log_dir='./logs',
                          histogram_freq=0,
                          write_graph=True,
                          write_images=True)

history = lstmae.fit(input_train,input_train, epochs=1000, batch_size=64, verbose=1, validation_data=(input_test, input_test) )

#Modell Accuracy
plt.plot(history.history['accuracy'])
plt.plot(history.history['val_accuracy'])
plt.title('Modell accuracy')
plt.ylabel('accuracy')
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
plt.show()

#Modell Loss
plt.plot(history.history['loss'])
plt.plot(history.history['val_loss'])
plt.title('Modell Loss')
plt.ylabel('loss')
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper right');

#print loss
#print val_loss

if args.test:
    preds = lstmae.predict(input_test)

input_test = Variable(torch.Tensor(input_test).float())
recon_test = Variable(torch.Tensor(preds).float())

"""Evaluierung"""

predicted_time, predicted_activity, true_time, true_activity = getError(recon_test, input_test, pad_index_test)

def plotConfusionMaxtrix(error_df, threshold, variable='Activity'):
    LABELS = ['Normal', 'Anomaly']
    y_pred = [1 if e > threshold else 0 for e in error_df.Error.values]
    
    if variable == 'Activity':
        matrix = confusion_matrix(error_df.ActivityLabel.astype('uint8'), y_pred)
    else:
        matrix = confusion_matrix(error_df.TimeLabel.astype('uint8'), y_pred)
        
    plt.figure(figsize=(7, 7))
    sns.heatmap(matrix, xticklabels=LABELS, yticklabels=LABELS, annot=True, fmt="d");
    plt.title('Confusion matrix of {}'.format(variable))
    plt.ylabel('True class')
    plt.xlabel('Predicted class')
    plt.show()

def eval(error_df, threshold, variable='Activity'):
    y_pred = [1 if e > threshold else 0 for e in error_df.Error.values]
    
    if variable=='Activity':
        y_true = error_df.ActivityLabel.astype('uint8')
    else:
        y_true = error_df.TimeLabel.astype('uint8')
    
    score = precision_recall_fscore_support(y_true, y_pred, average='binary')
        
    print('Evaluation of {}'.format(variable))
    print('Precision: {:.2f}'.format(score[0]))
    print('Recall: {:.2f}'.format(score[1]))
    print('Fscore: {:.2f}'.format(score[2]))
    #print('Support: {:.2f}'.format(score[3]))

"""Evaluation Aktivitäten"""

error = np.mean(np.power(true_activity - predicted_activity, 2), axis = 1)
error_activity_df = pd.DataFrame({'Error': error,
                                  'ActivityLabel': activity_label_test})

error_activity_df.head()

precision, recall, th = precision_recall_curve(error_activity_df.ActivityLabel, error_activity_df.Error, pos_label=1)
plt.figure(figsize=(20, 5))
plt.plot(recall, precision, 'b', label='Precision-Recall curve')
plt.title('Recall vs Precision')
plt.xlabel('Recall')
plt.ylabel('Precision')
plt.show()

activity_threshold = np.mean(error_activity_df['Error'])
print('Threshold of Activity: {}'.format(activity_threshold))

plotConfusionMaxtrix(error_activity_df, activity_threshold, variable='Activity')

plotOverlapReconstructionError(error_activity_df, variable='Activity', save=True)

plotReconstructionError(error_activity_df)

eval(error_activity_df, activity_threshold, variable='Activity')

fpr, tpr, thresholds = roc_curve(error_activity_df.ActivityLabel, error_activity_df.Error, pos_label=1)
roc_auc = auc(fpr, tpr)

plt.title('Receiver Operating Characteristic')
plt.plot(fpr, tpr, label='AUC = %0.4f'% roc_auc)
plt.legend(loc='lower right')
plt.plot([0,1],[0,1],'r--')
plt.xlim([-0.001, 1])
plt.ylim([0, 1.001])
plt.ylabel('True Positive Rate')
plt.xlabel('False Positive Rate')
#plt.savefig(args.output_dir+'ROC_Act.png')
plt.show();

"""Argmax"""

# evaluate based on classification
predicted_act_df = pd.DataFrame(data=predicted_activity, columns=list(true_act))
predicted_act_label = predicted_act_df.idxmax(axis=1)
true_act_label = true_act.idxmax(axis=1)
predicted_time_label = [0 if a==b else 1 for a, b in zip(true_act_label,predicted_act_label)]

score = precision_recall_fscore_support(error_activity_df.ActivityLabel.astype('uint8'), predicted_time_label, average='binary')
    
print('-------Evaluation of Activity-------')
print('\n')
print('--Weighted Evaluation--')
print('Evaluation')
print('Precision: {:.2f}'.format(score[0]))
print('Recall: {:.2f}'.format(score[1]))
print('Fscore: {:.2f}'.format(score[2]))
print('\n')
score_1 = precision_recall_fscore_support(error_activity_df.ActivityLabel.astype('uint8'), predicted_time_label)
print('--Evaluation for each class--')
print('Normal')
print('Precision: {:.2f}'.format(score_1[0][0]))
print('Recall: {:.2f}'.format(score_1[1][0]))
print('Fscore: {:.2f}'.format(score_1[2][0]))
print('\n')
print('Anomaly')
print('Precision: {:.2f}'.format(score_1[0][1]))
print('Recall: {:.2f}'.format(score_1[1][1]))
print('Fscore: {:.2f}'.format(score_1[2][1]))

from sklearn.metrics import accuracy_score
accuracy_score(true_act_label, predicted_act_label)