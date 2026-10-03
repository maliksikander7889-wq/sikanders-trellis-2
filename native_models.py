"""Load weights without first allocating a second, randomly initialized model."""
def load_checkpoint(factory, model_file, model_args):
    from accelerate import init_empty_weights
    from safetensors.torch import load_file
    with init_empty_weights(include_buffers=False):
        model = factory(**model_args)
    target_dtypes = {name: value.dtype for name, value in model.named_parameters()}
    state = load_file(model_file)
    for name, value in state.items():
        dtype = target_dtypes.get(name)
        if dtype is not None and value.dtype != dtype:
            state[name] = value.to(dtype=dtype)
    model.load_state_dict(state, strict=False, assign=True)
    missing = [name for name, value in list(model.named_parameters()) + list(model.named_buffers()) if value.is_meta]
    if missing:
        raise RuntimeError(f"Checkpoint is missing required parameters: {missing[:10]}")
    return model
