import json
import os
import re
import sys
import zlib
from typing import Callable, Optional, TextIO
from transformers import AutoTokenizer, AutoModelForTokenClassification
from transformers import pipeline
tokenizer = AutoTokenizer.from_pretrained("dslim/bert-base-NER")
model = AutoModelForTokenClassification.from_pretrained("dslim/bert-base-NER")

nlp = pipeline("ner", model=model, tokenizer=tokenizer)

import re
from collections import defaultdict

def combine_entities(entities):
    if not entities:
        return []

    combined_entities = []
    current_combined = entities[0].copy()

    for i in range(1, len(entities)):
        prev_entity = entities[i - 1]
        curr_entity = entities[i]

        # Check if we can combine
        if prev_entity['end'] >= curr_entity['start'] - 1:
            # Extend the current_combined entry
            current_combined['word'] += ' ' + curr_entity['word']
            current_combined['end'] = curr_entity['end']  # Update end to the current entity's end
            current_combined['index'] = min(current_combined['index'], curr_entity['index'])  # Update index if needed
        else:
            # Add the combined entity to the list and start a new combination
            combined_entities.append(current_combined)
            current_combined = curr_entity.copy()

    # Append the last combined entity
    combined_entities.append(current_combined)

    return combined_entities


def anonymize_text(ner_output, input_text):
    """
    Anonymizes person and organization names in the text based on NER output.

    Args:
    - ner_output (list): List of dictionaries from NER model.
    - input_text (str): Original text to be anonymized.

    Returns:
    - str: Anonymized text.
    """

    # Maps to hold unique replacements for PERSON and ORGANIZATION
    person_map = {}
    org_map = {}
    person_counter = 1
    org_counter = 1

    # Gather entities and their positions
    entities_to_replace = []
    for entity in ner_output:
        if entity["entity"].startswith("B-PER") or entity["entity"].startswith("I-PER"):
            if entity["word"] not in person_map:
                person_map[entity["word"]] = f"Max{person_counter}"
                person_counter += 1
            replacement = person_map[entity["word"]]
        elif entity["entity"].startswith("B-ORG") or entity["entity"].startswith("I-ORG"):
            if entity["word"] not in org_map:
                org_map[entity["word"]] = f"Firma{org_counter}"
                org_counter += 1
            replacement = org_map[entity["word"]]
        else:
            continue
        entities_to_replace.append((entity["start"], entity["end"], replacement))

    # Sort replacements by start position to apply them in order
    entities_to_replace.sort(key=lambda x: x[0])

    # Replace text based on entities
    anonymized_text = ""
    last_index = 0
    for start, end, replacement in entities_to_replace:
        anonymized_text += input_text[last_index:start] + replacement
        last_index = end
    anonymized_text += input_text[last_index:]

    return anonymized_text

LANGUAGES = {
    "en": "english",
    "zh": "chinese",
    "de": "german",
    "es": "spanish",
    "ru": "russian",
    "ko": "korean",
    "fr": "french",
    "ja": "japanese",
    "pt": "portuguese",
    "tr": "turkish",
    "pl": "polish",
    "ca": "catalan",
    "nl": "dutch",
    "ar": "arabic",
    "sv": "swedish",
    "it": "italian",
    "id": "indonesian",
    "hi": "hindi",
    "fi": "finnish",
    "vi": "vietnamese",
    "he": "hebrew",
    "uk": "ukrainian",
    "el": "greek",
    "ms": "malay",
    "cs": "czech",
    "ro": "romanian",
    "da": "danish",
    "hu": "hungarian",
    "ta": "tamil",
    "no": "norwegian",
    "th": "thai",
    "ur": "urdu",
    "hr": "croatian",
    "bg": "bulgarian",
    "lt": "lithuanian",
    "la": "latin",
    "mi": "maori",
    "ml": "malayalam",
    "cy": "welsh",
    "sk": "slovak",
    "te": "telugu",
    "fa": "persian",
    "lv": "latvian",
    "bn": "bengali",
    "sr": "serbian",
    "az": "azerbaijani",
    "sl": "slovenian",
    "kn": "kannada",
    "et": "estonian",
    "mk": "macedonian",
    "br": "breton",
    "eu": "basque",
    "is": "icelandic",
    "hy": "armenian",
    "ne": "nepali",
    "mn": "mongolian",
    "bs": "bosnian",
    "kk": "kazakh",
    "sq": "albanian",
    "sw": "swahili",
    "gl": "galician",
    "mr": "marathi",
    "pa": "punjabi",
    "si": "sinhala",
    "km": "khmer",
    "sn": "shona",
    "yo": "yoruba",
    "so": "somali",
    "af": "afrikaans",
    "oc": "occitan",
    "ka": "georgian",
    "be": "belarusian",
    "tg": "tajik",
    "sd": "sindhi",
    "gu": "gujarati",
    "am": "amharic",
    "yi": "yiddish",
    "lo": "lao",
    "uz": "uzbek",
    "fo": "faroese",
    "ht": "haitian creole",
    "ps": "pashto",
    "tk": "turkmen",
    "nn": "nynorsk",
    "mt": "maltese",
    "sa": "sanskrit",
    "lb": "luxembourgish",
    "my": "myanmar",
    "bo": "tibetan",
    "tl": "tagalog",
    "mg": "malagasy",
    "as": "assamese",
    "tt": "tatar",
    "haw": "hawaiian",
    "ln": "lingala",
    "ha": "hausa",
    "ba": "bashkir",
    "jw": "javanese",
    "su": "sundanese",
    "yue": "cantonese",
}

# language code lookup by name, with a few language aliases
TO_LANGUAGE_CODE = {
    **{language: code for code, language in LANGUAGES.items()},
    "burmese": "my",
    "valencian": "ca",
    "flemish": "nl",
    "haitian": "ht",
    "letzeburgesch": "lb",
    "pushto": "ps",
    "panjabi": "pa",
    "moldavian": "ro",
    "moldovan": "ro",
    "sinhalese": "si",
    "castilian": "es",
}

LANGUAGES_WITHOUT_SPACES = ["ja", "zh"]

system_encoding = sys.getdefaultencoding()

if system_encoding != "utf-8":

    def make_safe(string):
        # replaces any character not representable using the system default encoding with an '?',
        # avoiding UnicodeEncodeError (https://github.com/openai/whisper/discussions/729).
        return string.encode(system_encoding, errors="replace").decode(system_encoding)

else:

    def make_safe(string):
        # utf-8 can encode any Unicode code point, so no need to do the round-trip encoding
        return string


def exact_div(x, y):
    assert x % y == 0
    return x // y


def str2bool(string):
    str2val = {"True": True, "False": False}
    if string in str2val:
        return str2val[string]
    else:
        raise ValueError(f"Expected one of {set(str2val.keys())}, got {string}")


def optional_int(string):
    return None if string == "None" else int(string)


def optional_float(string):
    return None if string == "None" else float(string)


def compression_ratio(text) -> float:
    text_bytes = text.encode("utf-8")
    return len(text_bytes) / len(zlib.compress(text_bytes))


def format_timestamp(
    seconds: float, always_include_hours: bool = False, decimal_marker: str = "."
):
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)

    hours = milliseconds // 3_600_000
    milliseconds -= hours * 3_600_000

    minutes = milliseconds // 60_000
    milliseconds -= minutes * 60_000

    seconds = milliseconds // 1_000
    milliseconds -= seconds * 1_000

    hours_marker = f"{hours:02d}:" if always_include_hours or hours > 0 else ""
    return (
        f"{hours_marker}{minutes:02d}:{seconds:02d}{decimal_marker}{milliseconds:03d}"
    )


class ResultWriter:
    extension: str

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def __call__(self, result: dict, audio_path: str, options: dict):
        audio_basename = os.path.basename(audio_path)
        audio_basename = os.path.splitext(audio_basename)[0]
        output_path = os.path.join(
            self.output_dir, audio_basename + "." + self.extension
        )

        with open(output_path, "w", encoding="utf-8") as f:
            self.write_result(result, file=f, options=options)

    def write_result(self, result: dict, file: TextIO, options: dict):
        raise NotImplementedError


class WriteTXT(ResultWriter):
    extension: str = "txt"

    def write_result(self, result: dict, file: TextIO, options: dict):
        for segment in result["segments"]:
            print(segment["text"].strip(), file=file, flush=True)


class SubtitlesWriter(ResultWriter):
    always_include_hours: bool
    decimal_marker: str

    def iterate_result(self, result: dict, options: dict):
        raw_max_line_width: Optional[int] = options["max_line_width"]
        max_line_count: Optional[int] = options["max_line_count"]
        highlight_words: bool = options["highlight_words"]
        max_line_width = 1000 if raw_max_line_width is None else raw_max_line_width
        preserve_segments = max_line_count is None or raw_max_line_width is None

        if len(result["segments"]) == 0:
            return

        def iterate_subtitles():
            line_len = 0
            line_count = 1
            # the next subtitle to yield (a list of word timings with whitespace)
            subtitle: list[dict] = []
            times = []
            last = result["segments"][0]["start"]
            for segment in result["segments"]:
                for i, original_timing in enumerate(segment["words"]):
                    timing = original_timing.copy()
                    long_pause = not preserve_segments
                    if "start" in timing:
                        long_pause = long_pause and timing["start"] - last > 3.0
                    else:
                        long_pause = False
                    has_room = line_len + len(timing["word"]) <= max_line_width
                    seg_break = i == 0 and len(subtitle) > 0 and preserve_segments
                    if line_len > 0 and has_room and not long_pause and not seg_break:
                        # line continuation
                        line_len += len(timing["word"])
                    else:
                        # new line
                        timing["word"] = timing["word"].strip()
                        if (
                            len(subtitle) > 0
                            and max_line_count is not None
                            and (long_pause or line_count >= max_line_count)
                            or seg_break
                        ):
                            # subtitle break
                            yield subtitle, times
                            subtitle = []
                            times = []
                            line_count = 1
                        elif line_len > 0:
                            # line break
                            line_count += 1
                            timing["word"] = "\n" + timing["word"]
                        line_len = len(timing["word"].strip())
                    subtitle.append(timing)
                    times.append((segment["start"], segment["end"], segment.get("speaker")))
                    if "start" in timing:
                        last = timing["start"]
            if len(subtitle) > 0:
                yield subtitle, times

        if "words" in result["segments"][0]:
            for subtitle, _ in iterate_subtitles():
                sstart, ssend, speaker = _[0]
                subtitle_start = self.format_timestamp(sstart)
                subtitle_end = self.format_timestamp(ssend)
                if result["language"] in LANGUAGES_WITHOUT_SPACES:
                    subtitle_text = "".join([word["word"] for word in subtitle])
                else:
                    subtitle_text = " ".join([word["word"] for word in subtitle])
                has_timing = any(["start" in word for word in subtitle])

                # add [$SPEAKER_ID]: to each subtitle if speaker is available
                prefix = ""
                if speaker is not None:
                    prefix = f"[{speaker}]: "

                if highlight_words and has_timing:
                    last = subtitle_start
                    all_words = [timing["word"] for timing in subtitle]
                    for i, this_word in enumerate(subtitle):
                        if "start" in this_word:
                            start = self.format_timestamp(this_word["start"])
                            end = self.format_timestamp(this_word["end"])
                            if last != start:
                                yield last, start, prefix + subtitle_text

                            yield start, end, prefix + " ".join(
                                [
                                    re.sub(r"^(\s*)(.*)$", r"\1<u>\2</u>", word)
                                    if j == i
                                    else word
                                    for j, word in enumerate(all_words)
                                ]
                            )
                            last = end
                else:
                    yield subtitle_start, subtitle_end, prefix + subtitle_text
        else:
            for segment in result["segments"]:
                segment_start = self.format_timestamp(segment["start"])
                segment_end = self.format_timestamp(segment["end"])
                segment_text = segment["text"].strip().replace("-->", "->")
                if "speaker" in segment:
                    segment_text = f"[{segment['speaker']}]: {segment_text}"
                yield segment_start, segment_end, segment_text

    def format_timestamp(self, seconds: float):
        return format_timestamp(
            seconds=seconds,
            always_include_hours=self.always_include_hours,
            decimal_marker=self.decimal_marker,
        )


class WriteVTT(SubtitlesWriter):
    extension: str = "vtt"
    always_include_hours: bool = False
    decimal_marker: str = "."

    def write_result(self, result: dict, file: TextIO, options: dict):
        print("WEBVTT\n", file=file)
        for start, end, text in self.iterate_result(result, options):
            print(f"{start} --> {end}\n{text}\n", file=file, flush=True)

        txt_filename = file.name.replace('.vtt', '-v.txt')
        with open(txt_filename, 'w') as txt_file:
            # import pdb; pdb.set_trace()
            for _, _, text in self.iterate_result(result, options):
                text = text.replace(': ', '\n').replace('[', '').replace(']', ':')
                print(f"{text}\n", file=txt_file, flush=True)

        text = "\n\n".join([text for _, _, text in self.iterate_result(result, options)])
        replaced_txt_filename = file.name.replace('.vtt', '-v3.txt')
        with open(replaced_txt_filename, 'w') as replaced_txt_file:
            replaced_txt_file.write(anonymize_text(combine_entities(nlp(text)), text))

class WriteSRT(SubtitlesWriter):
    extension: str = "srt"
    always_include_hours: bool = True
    decimal_marker: str = ","

    def write_result(self, result: dict, file: TextIO, options: dict):
        for i, (start, end, text) in enumerate(
            self.iterate_result(result, options), start=1
        ):
            print(f"{i}\n{start} --> {end}\n{text}\n", file=file, flush=True)


class WriteTSV(ResultWriter):
    """
    Write a transcript to a file in TSV (tab-separated values) format containing lines like:
    <start time in integer milliseconds>\t<end time in integer milliseconds>\t<transcript text>

    Using integer milliseconds as start and end times means there's no chance of interference from
    an environment setting a language encoding that causes the decimal in a floating point number
    to appear as a comma; also is faster and more efficient to parse & store, e.g., in C++.
    """

    extension: str = "tsv"

    def write_result(self, result: dict, file: TextIO, options: dict):
        print("start", "end", "text", sep="\t", file=file)
        for segment in result["segments"]:
            print(round(1000 * segment["start"]), file=file, end="\t")
            print(round(1000 * segment["end"]), file=file, end="\t")
            print(segment["text"].strip().replace("\t", " "), file=file, flush=True)

class WriteAudacity(ResultWriter):
    """
    Write a transcript to a text file that audacity can import as labels.
    The extension used is "aud" to distinguish it from the txt file produced by WriteTXT.
    Yet this is not an audacity project but only a label file!
    
    Please note : Audacity uses seconds in timestamps not ms! 
    Also there is no header expected.

    If speaker is provided it is prepended to the text between double square brackets [[]].
    """

    extension: str = "aud"    

    def write_result(self, result: dict, file: TextIO, options: dict):
        ARROW = "	"
        for segment in result["segments"]:
            print(segment["start"], file=file, end=ARROW)
            print(segment["end"], file=file, end=ARROW)
            print( ( ("[[" + segment["speaker"] + "]]") if "speaker" in segment else "") + segment["text"].strip().replace("\t", " "), file=file, flush=True)

            

class WriteJSON(ResultWriter):
    extension: str = "json"

    def write_result(self, result: dict, file: TextIO, options: dict):
        json.dump(result, file, ensure_ascii=False)


def get_writer(
    output_format: str, output_dir: str
) -> Callable[[dict, TextIO, dict], None]:
    writers = {
        "txt": WriteTXT,
        "vtt": WriteVTT,
        "srt": WriteSRT,
        "tsv": WriteTSV,
        "json": WriteJSON,
    }
    optional_writers = {
        "aud": WriteAudacity,
    }

    if output_format == "all":
        all_writers = [writer(output_dir) for writer in writers.values()]

        def write_all(result: dict, file: TextIO, options: dict):
            for writer in all_writers:
                writer(result, file, options)

        return write_all

    if output_format in optional_writers:
        return optional_writers[output_format](output_dir)
    return writers[output_format](output_dir)

def interpolate_nans(x, method='nearest'):
    if x.notnull().sum() > 1:
        return x.interpolate(method=method).ffill().bfill()
    else:
        return x.ffill().bfill()
