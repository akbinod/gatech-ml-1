from collections import namedtuple
import os
import numpy as np
SEED = 0
np.random.seed(SEED)
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn import preprocessing
from sklearn.preprocessing import LabelEncoder, StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline,Pipeline
from sklearn.metrics import mean_squared_error, r2_score, f1_score
from sklearn.metrics import roc_curve, auc
from sklearn.metrics import accuracy_score
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import learning_curve
from sklearn.model_selection import ShuffleSplit
from matplotlib import pyplot as plt
from sklearn.model_selection import learning_curve #, ShuffleSplit

import joblib

import akbinod
from akbinod.Utils.TimedFunction import TimedFunction as tf
from learners.constants import LearnerMode


class BaseLearner():
	def __init__(self, learner_params):
		self.learner_params = learner_params
		# set later
		self.clf = None
		self.train_results = []
		self.test_results = []

		if(self.learner_params.validate_files()):
			if self.learner_params.mode == "raw":
				self.load_raw_data()
			elif self.learner_params.mode == "train":
				self.load_training_data()
			else:
				self.load_inference_data()

	def load_raw_data(self,debug=False, save_intermediate=False):
		# load the csv file, and split it into the train and test bits
		self.data = pd.read_csv(self.learner_params.data_path,sep=self.learner_params.data_separator)
		y = self.data[self.learner_params.learning_target]
		X = self.data.drop(self.learner_params.learning_target, axis=1)
		if(debug):
			print(self.data.head)
			print(self.data.shape)
			print(self.data.describe())

		# grab numeric features to scale (going to be needed by KNN and SVM)
		numeric_features = self.data.select_dtypes(include=['int64', 'float64']).columns
		numeric_transformer = Pipeline(steps=[
    									('imputer', SimpleImputer(strategy='median')),
    									('scaler', StandardScaler())]
										)
		# grab categorical features to encode (other than the learning target)
		categorical_features = self.data.select_dtypes(include=['object']).drop(self.learner_params.learning_target, axis=1).columns
		categorical_transformer = Pipeline(steps=[
    									('imputer', SimpleImputer(strategy='constant', fill_value='missing'))
    									, ('onehot', OneHotEncoder(handle_unknown='ignore'))
										]
										)

		preprocessor = ColumnTransformer(transformers=[
        								('num', numeric_transformer, numeric_features)
        								, ('cat', categorical_transformer, categorical_features)
										# , ('tar', target_transformer, target)
										]
										)
		X = preprocessor.fit_transform(X)

		target_transformer = preprocessing.LabelEncoder()
		y = target_transformer.fit_transform(y)

		# split the data into the train and test set
		# stratify it on the learning target so that the test set is
		# representative of the learning set
		self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(X, y,
														test_size=0.2,
														random_state=SEED,
														stratify=y)
		if save_intermediate:
			# persist the training and testing data separately
			# this is done just once for each raw file,
			# and then we'll take several different stabs at training later
			joblib.dump(self.X_train,self.learner_params.train_file + ".X")
			joblib.dump(self.y_train,self.learner_params.train_file + ".y")
			joblib.dump(self.X_test,self.learner_params.test_file + ".X")
			joblib.dump(self.y_test,self.learner_params.test_file + ".y")

	def load_training_data(self):
		self.X_train = joblib.load(self.learner_params.train_file + ".X")
		self.y_train = joblib.load(self.learner_params.train_file + ".y")
		# we'll want the test data too
		self.X_test = joblib.load(self.learner_params.test_file + ".X")
		self.y_test = joblib.load(self.learner_params.test_file + ".y")
		# this needs to be rebuilt
		self.model = None

	def load_inference_data():
		self.load_training_data()
		self.model = joblib.load(self.learner_params.model_file)

	def serialize(self):
		# saves the trained model
		joblib.dump(self.model,self.learner_params.model_file)

	@tf(True)
	def train(self):

		# 7. Tune model using cross-validation pipeline
		self.model.fit(self.X_train, self.y_train)
		# do we really need the next line if refit == True
		# self.model.refit()
		pred = self.model.predict(self.X_train)
		if self.learner_params.learner_mode == LearnerMode.regression:
			self.r2_score_train = r2_score(self.y_train, pred)
		else:
			# labels=['poor','fair','good','great']
			self.f1_score_train = f1_score(self.y_train, pred,average='weighted')

			# false_positive_rate, true_positive_rate, thresholds = roc_curve(self.y_train, pred)
			# self.roc_auc_train = auc(false_positive_rate, true_positive_rate)

		# self.train_results.append(roc_auc)
		# 10. Save model for future use
		self.serialize()

	@tf(True)
	def infer(self, debug=False):

		# 9. Evaluate model pipeline on test data
		pred = self.model.predict(self.X_test)
		if self.learner_params.learner_mode == LearnerMode.regression:
			self.r2_score_test = r2_score(self.y_test, pred)
		else:
			self.f1_score_test = f1_score(self.y_test, pred,average='weighted')
			# false_positive_rate, true_positive_rate, thresholds = roc_curve(self.y_test, pred)
			# self.roc_auc_test = auc(false_positive_rate, true_positive_rate)

		# self.test_results.append(roc_auc)

		if debug:
			if self.learner_params.learner_mode == LearnerMode.regression:
				print (f"r2 train, test: {self.r2_score_train}, {self.r2_score_test}")
			else:
				print (f"f1 train, test: {self.f1_score_train}, {self.f1_score_test}")
				print(self.model.best_params_)
				# print (f"roc_auc train, test: {self.roc_auc_train}, {self.roc_auc_test}")
		return (self.f1_score_train, self.f1_score_test)

	def plot_learning_curve(self
							# , axes=None
						):
		"""
		Generate 3 plots: the test and training learning curve, the training
		samples vs fit times curve, the fit times vs score curve.

		Parameters
		----------
		estimator : object type that implements the "fit" and "predict" methods
			An object of that type which is cloned for each validation.

		title : string
			Title for the chart.

		axes : array of 3 axes, optional (default=None)
			Axes to use for plotting the curves.

		ylim : tuple, shape (ymin, ymax), optional
			Defines minimum and maximum yvalues plotted.

		n_jobs : int or None, optional (default=None)
			Number of jobs to run in parallel.
			``None`` means 1 unless in a :obj:`joblib.parallel_backend` context.
			``-1`` means using all processors. See :term:`Glossary <n_jobs>`
			for more details.

		train_sizes : array-like, shape (n_ticks,), dtype float or int
			Relative or absolute numbers of training examples that will be used to
			generate the learning curve. If the dtype is float, it is regarded as a
			fraction of the maximum size of the training set (that is determined
			by the selected validation method), i.e. it has to be within (0, 1].
			Otherwise it is interpreted as absolute sizes of the training sets.
			Note that for classification the number of samples usually have to
			be big enough to contain at least one sample from each class.
			(default: np.linspace(0.1, 1.0, 5))
		"""
		ylim=(0.2, 1.01)
		train_sizes=np.linspace(.1, 1.0, 5)

		train_sizes, train_scores, test_scores, fit_times, _ = learning_curve(
										self.model.best_estimator_, self.X_train
										, self.y_train, cv=self.learner_params.cv
										, train_sizes=train_sizes
										, return_times=True
									)
		train_scores_mean = np.mean(train_scores, axis=1)
		train_scores_std = np.std(train_scores, axis=1)
		test_scores_mean = np.mean(test_scores, axis=1)
		test_scores_std = np.std(test_scores, axis=1)
		fit_times_mean = np.mean(fit_times, axis=1)
		fit_times_std = np.std(fit_times, axis=1)

		# if axes is None:
		_, axes = plt.subplots(1, 3, figsize=(20, 5))

		axes[0].set_title("Learning Curves - " + self.learner_params.learner_name)
		axes[0].set_xlabel("Training examples")
		axes[0].set_ylabel("Score")
		axes[0].set_ylim(*ylim)

		# train_sizes, train_scores, test_scores, fit_times, _ = learning_curve(
		# 						self.clf, self.X_train, self.y_train, cv=self.learner_params.cv
		# 						, n_jobs=n_jobs, train_sizes=train_sizes, return_times=True
		# 						)
		# train_scores_mean = np.mean(train_scores, axis=1)
		# train_scores_std = np.std(train_scores, axis=1)
		# test_scores_mean = np.mean(test_scores, axis=1)
		# test_scores_std = np.std(test_scores, axis=1)
		# fit_times_mean = np.mean(fit_times, axis=1)
		# fit_times_std = np.std(fit_times, axis=1)

		# Plot learning curve
		axes[0].grid()
		axes[0].fill_between(train_sizes, train_scores_mean - train_scores_std,
							train_scores_mean + train_scores_std, alpha=0.1,
							color="r")
		axes[0].fill_between(train_sizes, test_scores_mean - test_scores_std,
							test_scores_mean + test_scores_std, alpha=0.1,
							color="g")
		axes[0].plot(train_sizes, train_scores_mean, 'o-', color="r",
					label="Training score")
		axes[0].plot(train_sizes, test_scores_mean, 'o-', color="g",
					label="Cross-validation score")
		axes[0].legend(loc="best")

		# Plot n_samples vs fit_times
		axes[1].grid()
		axes[1].plot(train_sizes, fit_times_mean, 'o-')
		axes[1].fill_between(train_sizes, fit_times_mean - fit_times_std,
							fit_times_mean + fit_times_std, alpha=0.1)
		axes[1].set_xlabel("Training examples")
		axes[1].set_ylabel("fit_times")
		axes[1].set_title("Scalability of the model")

		# Plot fit_time vs score
		axes[2].grid()
		axes[2].plot(fit_times_mean, test_scores_mean, 'bo')
		axes[2].fill_between(fit_times_mean, test_scores_mean - test_scores_std,
							test_scores_mean + test_scores_std, alpha=0.1)
		axes[2].set_xlabel("fit_times")
		axes[2].set_ylabel("Score")
		axes[2].set_title("Performance of the model")

		return plt
