import soundfile as sf
import pedalboard as pb
import os
from numbers import Real
import re
import unicodedata


def normalize_text(value):
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    return (
        text.replace("\u2212", "-")
        .replace("\u202f", " ")
        .replace("\u00a0", " ")
        .strip()
        .lower()
    )


def extract_number(value):
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", normalize_text(value))
    return float(match.group()) if match else None


def set_parameter(plugin, param_id, user_input):
    if param_id not in plugin.parameters:
        print(f"Warning: Parameter '{param_id}' not found in plugin '{plugin.name}'.")
        return False

    try:
        setattr(plugin, param_id, user_input)
        return True
    except Exception:
        pass

    param_meta = plugin.parameters[param_id]
    valid_values = getattr(param_meta, "valid_values", None)

    if valid_values:
        normalized_input = normalize_text(user_input)
        selected_value = next(
            (
                value
                for value in valid_values
                if normalize_text(value) == normalized_input
            ),
            None,
        )

        input_number = extract_number(user_input)
        if selected_value is None and input_number is not None:
            numeric_values = [
                (abs(number - input_number), value)
                for value in valid_values
                if (number := extract_number(value)) is not None
            ]
            if numeric_values:
                selected_value = min(numeric_values, key=lambda item: item[0])[1]

        if selected_value is not None:
            try:
                setattr(plugin, param_id, selected_value)
                return True
            except Exception:
                pass

    if isinstance(user_input, Real):
        try:
            setattr(plugin, param_id, float(user_input))
            return True
        except Exception:
            pass

    print(
        f"Warning: Could not set '{param_id}' on plugin "
        f"'{plugin.name}' from {user_input!r}."
    )
    return False


if __name__ == "__main__":
    # Read and cast explicitly to 32-bit float
    audio, sample_rate = sf.read("1.wav")
    audio = audio.astype("float32")

    # Load all plugins
    noise = pb.load_plugin("rnnoise.vst3")
    eq = pb.load_plugin("FreeEQ8.vst3")
    compressor = pb.load_plugin("ZL Compressor.vst3")
    gate = pb.load_plugin("BPGate.vst3")

    # Set parameters
    set_parameter(gate, "threshold", -24)

    # Process
    chain = pb.Pedalboard([noise, eq, compressor, gate])
    effected = chain(audio, sample_rate)

    # Save
    sf.write("1_processed.wav", effected, sample_rate)
    print("Wrote file successfully.")

    # Instant kill to prevent trailing background threads from keeping the console alive
    os._exit(0)
