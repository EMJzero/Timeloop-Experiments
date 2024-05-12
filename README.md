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
-   Install Accelergy's estimation tables:
    ```
    accelergyTables -r Timeloop-Experiments/transformer_gemmini/free_data
    accelergyTables -r Timeloop-Experiments/transformer_pim/PIM_estimation_tables
    ```
    Remember now that to modify any metric fetched from those tables, the path above is where you need to modify them, ignore the copies of the same folders under `transformer_pim_backup`.

## Documentation

For details on the the structure and function of the various `.yaml` files and the meaning of all parameters used within them, please refer to those sources:
-   [Timeloop Documentation](https://timeloop.csail.mit.edu/v4)
-   [Timeloop Tutorials](https://accelergy.mit.edu/tutorial.html)

The documentation, as of the time of writing, is anything but exhaustive, henceforth be prepared to read some code to understand all the details. In particular [Timeloop's src/model](https://github.com/NVlabs/timeloop/tree/master/src/model) folder contains all the components used in the `arch.yaml` files, and searching through their respective `ParseSpecs` methods (ctrl+f them) often helps where the documentation doesn't.

## Running The Experiements

The two main active examples are **`transformer_pim`** and **`transformer_gemmini`**, all other ones may make use of the outdated Timeloop-v3 or not work entirely.

Before running any example, check out its `mapper.yaml` file, usually under the `mapper` folder. In there, you should set `num_threads` to the number of logical processors in your machine. Furthermore, consider also setting `victory_condition` to a few thousand attempts, this the number of not-improving mappings to encounter before a thread stops, the higher this is, the more likely Timeloop is to find the optimal mapping.

Unfortunately **root privileges** are required to run those scripts, due to the inner workings of Accelergy. This also implies that any Python package required shall be installed with `sudo pip install` (no matter how much Pip hates it :sweat_smile:).<br>

Also, while it is possible to invoke Timeloop directly, without using its Python fronted (`timeloopfe`), this is the preferred method as of Timeloop-v4.


### <a name="MSE"></a> Map-Space Exploration (MSE)

To run MSE, you just need to run its Python main file in the relative example folder:
```sh
cd Timeloop-Experiments/transformer_pim
sudo python3 run.py <layer> [optional-fusion-level]
```
This will run Timeloop's mapper for the provided layer of the BERT Transformer architecture, a directory like `outputs_<layer>_<optional-fusion-level>` will be created for all results. The most relevant outputs being `timeloop-mapper.accelergy.log` for debugging in case the mapper did not run, `timeloop-mapper.map.txt` for the best mapping found (also printed at the end of the Python script), and `timeloop-mapper.stats.txt` for the full mapping statistics.<br>
Please note that unless `victory_condition` is specified and low enough, forcefully terminating Timeloop (ctrl+C) is the intended way to stop the exploration.

Lastly, for a full list of the functionalities of `run.py`, please run:
```sh
python3 run.py
python3 run.py -h
```


### <a name="HWDSE"></a> Hardware Design Space Exploration (HWDSE)

To run an example, first of all edit the `hwdse_run.py` script to select the HW configurations to test, look for a dictionary array called `hw_configs`:

```sh
cd Timeloop-Experiments/transformer_pim
vim +$(grep -n -m1 "hw_configs" hwdse_run.py | cut -d: -f1) hwdse_run.py
```
The provided example configurations include all the architectural parameters that the script can automatically alter.
> As of the latest update, you can also **provide the configurations via a file** formatted as JSON, see the `-c` option and the `hw_configs.json` files for details. Note that onfigurations provided in this way override those hard-coded in the script.
> ```sh
> # an example usage:
> sudo python3 hwdse_run.py KTQ VScores softmax -c hw_configs.json -vc 3200 -t
> ```

Then, you just need to run the Python script:
```sh
# to run some selected layers
sudo python3 hwdse_run.py <layer1> ... <layerN> [optional-fusion-level]
# to run all layers
sudo python3 hwdse_run.py all [optional-fusion-level]
```
This will run Timeloop's mapper for each HW configuration and each provided layer of the BERT Transformer architecture, a `outputs_hwdse` directory will be created for all results. In there, there will be a folder for each tried configuration, numbered from 0 onward by default, each folder containing a sub-folder for each mapped layer (whose contents will be the same as in [MSE](#MSE)) and a `hw_config.json` file with a summary of the configuration and its final metrics.<br>
Relevant tuning nobs are the `-vs <num>` option, which allows to specify the `victory_condition` for Timeloop (a "good enough" value is 3200, while the default is 160 to speedup testing), and the `-mx` option, which rather than testing only the provided HW configurations, also considers all their possible cross-overs (use with care, as the number of configurations can blow up very quickly :grimacing:).<br>
Finally, `-so` can be used to view the results from a previous run of HWDSE, while `-t` presents the results in a more comfortable table.

Lastly, for a full list of the functionalities of `hwdse_run.py`, please run:
```sh
python3 hwdse_run.py
python3 hwdse_run.py -h
```
