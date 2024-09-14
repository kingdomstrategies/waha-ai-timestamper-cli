import os

import torch
from halo import Halo

from constants import dict_name, dict_url, model_name, model_url
from mms.align_utils import DEVICE, get_model_and_dict


def load_model():
    spinner = Halo(text="Downloading model...").start()
    if os.path.exists(model_name):
        spinner.info("Model already downloaded.")
    else:
        torch.hub.download_url_to_file(
            model_url,
            model_name,
        )
        spinner.succeed("Model downloaded.")
    assert os.path.exists(model_name)

    spinner.text = "Downloading dictionary..."
    spinner.start()

    if os.path.exists(dict_name):
        spinner.info("Dictionary already downloaded.")
    else:
        torch.hub.download_url_to_file(
            dict_url,
            dict_name,
        )
        spinner.succeed("Dictionary downloaded.")
    assert os.path.exists(dict_name)

    load_spinner = Halo(text="Loading model and dictionary...").start()
    model, dictionary = get_model_and_dict()
    dictionary["<star>"] = len(dictionary)
    model = model.to(DEVICE)
    load_spinner.succeed("Model and dictionary loaded. Ready to receive requests.")
    return model, dictionary
