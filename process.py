import soundfile as sf
import pedalboard as pb
import os
from numbers import Real
import re
import unicodedata
from pathlib import Path
import sys
import numpy as np
import time


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


def main():
    # Load all plugins
    noise = pb.load_plugin("rnnoise.vst3")  # type: ignore
    eq = pb.load_plugin("FreeEQ8.vst3")  # type: ignore
    compressor = pb.load_plugin("ZL Compressor.vst3")  # type: ignore
    gate = pb.load_plugin("renegate.vst3", initialization_timeout=50)  # type: ignore

    silence = np.zeros((2, 4096), dtype=np.float32)
    _ = gate(silence, 48000, reset=True)

    set_parameter(noise, "vad_threshold", 0.35)
    set_parameter(noise, "vad_grace_period_10ms_per_unit", 100)
    set_parameter(
        noise,
        "retroactive_vad_grace_period_10ms_per_unit",
        5,
    )
    set_parameter(noise, "bypass", False)

    set_parameter(eq, "band_1_type", "HighPass")
    set_parameter(eq, "band_1_freq", 75)
    set_parameter(eq, "band_1_q", 0.75)
    set_parameter(eq, "band_1_gain", 0)

    set_parameter(eq, "band_8_type", "HighShelf")
    set_parameter(eq, "band_8_freq", 8500)
    set_parameter(eq, "band_8_q", 1)
    set_parameter(eq, "band_8_gain", 0)

    set_parameter(eq, "band_8_dyn_on", True)
    set_parameter(eq, "band_8_threshold", -42)
    set_parameter(eq, "band_8_ratio", 4)
    set_parameter(eq, "band_8_attack", 10)
    set_parameter(eq, "band_8_release", 10)

    set_parameter(compressor, "threshold_db_threshold_db", -32)
    set_parameter(compressor, "ratio_ratio", 3.5)
    set_parameter(compressor, "attack_attack", 20)
    set_parameter(compressor, "release_release", 140)
    set_parameter(compressor, "makeup_gain_makeup_gain", 4.5)
    set_parameter(compressor, "oversample_oversample", "4x")

    set_parameter(gate, "threshold_db", -36)
    set_parameter(gate, "hold_ms", 10)
    set_parameter(gate, "release_ms", 150)
    set_parameter(gate, "attack_ms", 15)
    set_parameter(gate, "mix", 70)

    # print(gate._parameters)

    # Set parameters
    # set_parameter(gate, "threshold", -24)

    # Process
    # chain = pb.Pedalboard([noise, eq, compressor, gate])  # type: ignore

    if sys.argv.__len__() == 1:
        print("no directory inputed")
        os._exit(0)
        return

    directory = Path(Path.cwd()._str + sys.argv[1])

    Path(Path.cwd()._str + "/output").mkdir()

    i = 0
    for entry in directory.iterdir():
        print(entry.name)
        # Read and cast explicitly to 32-bit float
        audio, sample_rate = sf.read(entry, always_2d=True)
        audio = audio.astype("float32")

        # Ensure stereo before FreeEQ8
        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)

        peak = np.max(np.abs(audio))

        if peak > 0:
            audio = audio / peak  # Normalize to ±1.0

        # Reduce by 6 dB
        audio *= 10 ** (-6 / 20)

        # Process stereo-only plugins
        audio = noise(audio, sample_rate)
        audio = eq(audio, sample_rate)  # FreeEQ8 needs 2 channels
        audio = compressor(audio, sample_rate)
        audio = gate(audio, sample_rate)

        # Write final mono
        mono = audio.mean(axis=1)

        # Save
        sf.write(Path.cwd()._str + f"/output/{entry.name}.wav", mono, sample_rate)
        i += 1
        if i >= 10:
            break
    os._exit(0)


if __name__ == "__main__":
    main()
    os._exit(0)
    # Instant kill to prevent trailing background threads from keeping the console alive
