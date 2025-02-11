import torch
from surprise import Dataset as sDataset
from torch import Tensor
from torch.utils.data import Dataset as tDataset
import pandas as pd
from sklearn.model_selection import train_test_split
from data.dataset import Dataset as DS
import numpy as np


class Dataset(tDataset):
    def __init__(
        self,
        ratings_path: str = None,
        ut: int = 0,
        data=None,
        device=torch.device("cpu"),
    ):
        super(tDataset, self).__init__()

        if data == None:
            self.ds = DS(ratings_path, user_threshold=ut)
            self.data = torch.zeros((self.ds.n_users, self.ds.n_items))
        else:
            self.data = data
            for d in self.data:
                d.to(device)

    def __len__(self):
        return self.data.shape[0]

    def __getitem__(self, index) -> Tensor:
        return self.data[index]

    @property
    def n_items(self):
        return self.data.shape[1]

    @property
    def n_users(self):
        return self.data.shape[0]

    @property
    def ratings_scale(self):
        return 5

    def userKFold(self, n_splits=5, kind: str = "2-way"):
        for train, test in self.ds.userKFold(n_splits):

            train_data = torch.zeros((self.ds.n_users, self.ds.n_items))
            test_data = torch.zeros((self.ds.n_users, self.ds.n_items))

            for u, i, r in train:
                train_data[int(u)][int(i)] = float(r)

            for u, i, r in test:
                test_data[int(u)][int(i)] = float(r)

            train_data = train_data[train_data.sum(dim=1) != 0]
            test_data = test_data[test_data.sum(dim=1) != 0]
            if kind == "2-way":
                yield Dataset(data=train_data), Dataset(data=test_data)

            elif kind == "3-way":
                valid_data, test_data = train_test_split(
                    test_data, test_size=0.5, shuffle=True, random_state=42
                )
                yield (
                    Dataset(data=train_data),
                    Dataset(data=valid_data),
                    Dataset(data=test_data),
                )


class Trainset(tDataset):
    def __init__(self, path: str, device=torch.device("cpu")):
        torch.manual_seed(42)

        super(tDataset, self).__init__()

        df = pd.read_csv(path, header=None, index_col=None)

        self.data = torch.zeros(6040, 3416, 5)
        for row in df.itertuples():
            self.data[row[1]][row[2]][int(row[3]) - 1] = 1

        # remove all empty rows
        self.data = self.data[self.data.sum(dim=(1, 2)) != 0]

    def __len__(self):
        return self.data.shape[0]

    def __getitem__(self, index) -> Tensor:
        return self.data[index]

    @property
    def n_items(self):
        return self.data.shape[1]

    @property
    def n_users(self):
        return self.data.shape[0]

    @property
    def ratings_scale(self):
        return 5


class Testset(Trainset):
    def __init__(self, path: str, device=torch.device("cpu"), ratio: float = 0.2):
        super().__init__(path, device)

        self.foldin = torch.zeros_like(self.data)
        self.holdout = torch.zeros_like(self.data)

        # hold out data
        for i in range(len(self.data)):
            # find indicies of all ratings
            idx = self.data[i].nonzero()

            fi_idx, _ = train_test_split(idx, test_size=ratio, random_state=42)
            self.foldin[i][fi_idx] = self.data[i][fi_idx]

        self.holdout = self.data - self.foldin
        assert self.foldin.sum() + self.holdout.sum() == self.data.sum()

    def __len__(self):
        return super().__len__()

    def __getitem__(self, index):
        return self.foldin[index], self.holdout[index]


class LeaveOneOutSet(Trainset):
    def __init__(self, path: str, device=torch.device("cpu"), rt: float = 3.5):
        super().__init__(path, device)

        self.foldin = torch.zeros_like(self.data)
        self.holdout = torch.zeros_like(self.data)

        # hold out data
        for i in range(len(self.data)):
            # find indicies of all ratings
            idx = self.data[i].argmax(dim=1) + 1 > rt
            idx = idx.nonzero().flatten()
            if len(idx) == 0:
                continue
            ho_idx = np.random.choice(idx, size=1)
            self.foldin[i, ho_idx] = torch.zeros_like(self.foldin[i, ho_idx])
            # perserve the value in the holdout
            self.holdout[i, ho_idx] = self.data[i, ho_idx]

    def __len__(self):
        return super().__len__()

    def __getitem__(self, index):
        return self.foldin[index], self.holdout[index]


if __name__ == "__main__":
    testset = Testset("data/folds/1/valid.csv")
    lootestset = LeaveOneOutSet("data/folds/1/valid.csv")
