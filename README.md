# Timeloop Experiements - HPSR 2024 - Ronzani Marco

This is a set of experiments for the mapping of Transformer-based models on spatial architectures. [Timeloop](https://github.com/NVlabs/timeloop) is being used for both its map-space exploration capabilities and its analytical model, with also the support of [Accelergy](https://github.com/Accelergy-Project/accelergy). Target Transformer-based models include [BERT](https://arxiv.org/abs/1810.04805) (base and large) and [GPT-2](https://github.com/openai/gpt-2). Target architectures span from [Gemmini](https://github.com/ucb-bar/gemmini)-like systolic arrays and [Eyeriss](https://ieeexplore.ieee.org/document/7738524) like matrices of processing elements to [analog](https://ieeexplore.ieee.org/document/8802267) and [digital](https://ieeexplore.ieee.org/document/10067422) in-memory computing.

>DISCLAIMER: the structure of this repository is very likely to change in the future, anything you find here now is very much WORK-IN-PROGRESS and is NOT guaranteed to work, nor to produce correct results even if it does, hence critically judge any results you might get.

## Setup

The steps required to utilize the hereby examples are as follow:

-   Install the [Accelergy-Timeloop Infrastructure](https://github.com/Accelergy-Project/accelergy-timeloop-infrastructure), instructions are provided under "Native Install" in the linked repository's README. The only tested version of the tools is that as of commit [a9b57b6](https://github.com/Accelergy-Project/accelergy-timeloop-infrastructure/commit/a9b57b65a21f7672e87f67e9b54b1847d2df5b79).
-   Clone this repository:
    ```
    git clone https://github.com/EMJzero/Timeloop-Experiments.git
    ```
-   Install Accelergy's estimation tables for IMC:
    ```
    accelergyTables -r Timeloop-Experiments/transformer_pim/PIM_estimation_tables
    ```
    Remember now that to modify any metric fetched from those tables, the path above is where you need to modify them, ignore the copy of the same folder under `transformer_pim_backup`.

## Documentation

For details on the the structure and function of the various `.yaml` files and the meaning of all parameters used within them, please refer to those sources:
-   [Timeloop Documentation](https://timeloop.csail.mit.edu/v4)
-   [Timeloop Tutorials](https://accelergy.mit.edu/tutorial.html)

The documentation, as of the time of writing, is anything but exhaustive, henceforth be prepared to read some code to understand all the details. In particular [Timeloop's src/model](https://github.com/NVlabs/timeloop/tree/master/src/model) folder contains all the components used in the `arch.yaml` files, and searching through their respective `ParseSpecs` methods (ctrl+f them) often helps where the documentation doesn't.

## Running The Experiments

The two main active examples are **`transformer_pim`** and **`transformer_gemmini`**, all other ones may make use of the outdated Timeloop-v3 or not work entirely.

Before running any example, check out its `mapper.yaml` file, usually under the `mapper` folder. In there, you should set `num_threads` to the number of logical processors in your machine. Furthermore, consider also setting `victory_condition` to a few thousand attempts.

To run an example, you just need to run its Python main file:
```
cd Timeloop-Experiments/transformer_pim
sudo python3 run.py <layer> [optional-fusion-level]
```
This will run Timeloop's mapper for the provided layer of the BERT Transformer architecture, a directory like `outputs_layer_optional-fusion-level` will be created for all results. The most relevant outputs being `timeloop-mapper.accelergy.log` for debugging in case the mapper did not run, `timeloop-mapper.map.txt` for the best mapping found (also printed at the end of the python script), and `timeloop-mapper.stats.txt` for the full mapping statistics.<br>
Please note that unless `victory_condition` is specified and low enough, forcefully terminating Timeloop (ctrl+C) is the intended way to stop the exploration.

Unfortunately root privileges are required, due to the inner workings of Accelergy.<br>
Also, while it is possible to invoke Timeloop directly, this is the preferred method as of Timeloop-v4.

Lastly, for a full list of the functionalities of `run.py`, please run:
```
python3 run.py
python3 run.py -h
```