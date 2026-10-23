# Architectural Bugs

## 1. Critical: dataset recording and dataset loading do not agree on the episode set

- `experiments/record_sim_episodes.py:47-50` uses `episode_idx = -1` and `while episode_idx < num_episodes`, then increments at the top of the loop. That records `num_episodes + 1` successful files (`episode_0` through `episode_{num_episodes}`), not `num_episodes`.
- `experiments/imitate_episodes.py:54-56` and `experiments/utils.py:84-85` assume exactly `num_episodes` files and only ever read `episode_0` through `episode_{num_episodes-1}`.
- Result: the recorder and trainer disagree about what the dataset is. The extra file is silently ignored by training, so the persisted dataset is not the dataset the model actually trains on.

Impact:
- Reproducibility is broken.
- Re-recording into the same directory can leave stale files that look valid but are never consumed.
- Dataset size in config is no longer a trustworthy source of truth.

## 2. Critical: `/observations/type` is mandatory for training but invalid for most recorded tasks

- `experiments/record_sim_episodes.py:142-179` always creates `/observations/type`.
- For `mix_cube`, it stores `episode_idx % 2`, but for every other task it appends `None`.
- `experiments/record_sim_episodes.py:199-202` then writes that list into an HDF5 dataset.
- `experiments/utils.py:50` unconditionally reads `/observations/type` during training.

Result:
- Non-`mix_cube` tasks have a schema that is internally inconsistent: the field is required by the trainer, but the recorder populates it with values that are not a valid numeric label set.
- This makes the dataset format task-dependent in an undocumented way and couples the trainer to a partially broken extension.

Impact:
- `single_cube`, `single_torus`, `multiple_red`, `multiple_green`, and `multiple_blue` cannot be treated as first-class tasks under the current dataset contract.
- The project has no stable dataset schema shared across tasks.

## 3. High: reward computation depends on contact tuple ordering and is wrong in multiple environments

- `experiments/sim_env.py:166-167`, `214-215`, `257-264`, `308-311`
- `prototype_manipulator/sim_env.py:140-147`

There are two separate problems:

- Several reward checks only test one tuple ordering, for example `("red_box", "table") in all_contact_pairs`. MuJoCo contacts are not guaranteed to be reported in the semantic order the code expects.
- The torus-style checks use expressions like `((a, b) or (b, a)) in all_contact_pairs`. In Python, `(a, b) or (b, a)` always evaluates to the first tuple, so the reverse ordering is never checked at all.

Result:
- Success labels depend on incidental contact ordering instead of physical state.
- Recorded demonstrations, evaluation scores, and grasp success metrics can all be wrong.

Impact:
- This corrupts both data collection and benchmark reporting.
- Any model selection based on these rewards is unreliable.

## 4. High: the web order flow and manipulator flow have incompatible capacity and state models

- `prototype_web_interface/app.py:12, 29, 37-45` allows an unbounded cart and emits every selected item into the CSV.
- `prototype_manipulator/main.py:117-119` seeds the simulation with exactly two object poses.
- `prototype_manipulator/assets/bimanual_viperx_transfer_cube.xml:7-18` defines exactly two active object bodies.
- `prototype_manipulator/main.py:137-219` then iterates over every CSV row without resetting the scene between items.

Result:
- The web UI promises arbitrary order sizes, but the robot scene only contains two objects.
- A third ordered item has no corresponding object in the scene.
- Even the second item is executed on the mutated post-grasp scene from the first item, not on a fresh scene per order line.

Impact:
- The end-to-end prototype is not functionally correct for general cart usage.
- User-visible behavior diverges from the simulator’s actual capacity.

## 5. High: the Flask app stores cart state globally across all users and leaks generated files

- `prototype_web_interface/app.py:12` keeps a single module-level `cart`.
- `prototype_web_interface/app.py:37-45` writes each order to a new CSV in the working directory and immediately returns it with `send_file`, but never deletes it.

Result:
- All users share the same cart state inside one Flask process.
- Concurrent users can contaminate each other’s orders.
- Repeated orders accumulate orphan CSV files on disk.

Impact:
- The prototype is unsafe even as a demo in any multi-user or long-running deployment.
- State isolation and storage lifecycle are both missing.

## 6. Medium: prototype object spawning uses an invalid quaternion

- `prototype_manipulator/utils.py:45-54` returns object poses with quaternion `[0, 0, 0, 0]`.
- The same project’s XML keyframe uses a valid unit quaternion, for example `1 0 0 0` in `prototype_manipulator/assets/bimanual_viperx_transfer_cube.xml:50-53`.

Result:
- The pose generator does not satisfy the expected free-joint pose format for MuJoCo.
- Object initialization depends on undefined or engine-normalized behavior instead of a valid rotation.

Impact:
- Reset behavior can be unstable or misleading.
- Simulation correctness depends on accidental tolerance rather than a valid scene contract.
