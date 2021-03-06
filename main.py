import json
from learners import BaseLearner, RandomForest, LearnerParams, SVM
from learners import DecisionTree, KNearestNeighbors, BoostedTree, NeuralNetwork
from learners.constants import LearnerMode

SEED = 0

def process_files(paths, target):
	results = {}
	plots = []
	for data_path in paths:
		results[data_path] = {}
		params = LearnerParams(LearnerMode.classification, learning_target=target, data_path=data_path, cv = 5)
		results[data_path] = {}

		lrnr = DecisionTree(params)
		# lrnr = BoostedTree(params)
		# lrnr = KNearestNeighbors(params)
		# lrnr = SVM(params)
		# lrnr = NeuralNetwork(params)

		lrnr.train()
		res = lrnr.infer()
		results[data_path]['train'] = res[0]
		results[data_path]['test'] = res[1]
		results[data_path]['best_params'] = lrnr.model.best_params_
		plots.append(lrnr.plot_learning_curve())

	print(json.dumps(results))
	for plt in plots:
		plt.show()

def get_coffee_files():

	paths = []
	paths.append('./data/flavor-coffee.csv')
	paths.append('./data/flavor-coffee-no-altitude.csv')
	paths.append('./data/flavor-coffee-no-country-altitude.csv')
	paths.append('./data/flavor-coffee-no-region-altitude.csv')
	paths.append('./data/flavor-coffee-no-region-altitude-elevation.csv')
	return paths

def get_iris_files():
	return ['./data/iris-1.csv']

def get_wine_files():
	return ['./data/winequality.csv']

def main(get_coffee):
	# files = get_wine_files()

	if get_coffee:
		files = get_coffee_files()
		process_files(files, "target")
	else:
		files = get_iris_files()
		process_files(files, "Species")

if __name__ == "__main__":
	main(True)