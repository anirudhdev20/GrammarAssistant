import math
import re
from importlib import resources

from spacy.tokens import Doc, Token
from symspellpy import SymSpell, Verbosity
from wordfreq import zipf_frequency

from ..schemas import Issue, IssueSource, IssueType, Severity

WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'’-]*$")
SHORT_WORDS = {"a", "i", "an", "am", "as", "at", "be", "by", "do", "go", "he", "if", "in", "is", "it", "me", "my", "no", "of", "on", "or", "so", "to", "up", "us", "we"}
COMMON_MISSPELLINGS = {
    "teh",
    "recieve",
    "recieved",
    "recieving",
    "definately",
    "definetly",
    "seperate",
    "seperated",
    "occured",
    "occuring",
    "untill",
    "wich",
    "becuase",
    "beacuse",
    "freind",
    "freinds",
    "thier",
    "adress",
    "arguement",
    "begining",
    "calender",
    "changeing",
    "comming",
    "commited",
    "concious",
    "enviroment",
    "existance",
    "experiance",
    "familar",
    "finaly",
    "foriegn",
    "goverment",
    "gaurd",
    "happend",
    "harrass",
    "immediatly",
    "independant",
    "knowlege",
    "liason",
    "maintainance",
    "millenium",
    "neccessary",
    "necesary",
    "noticable",
    "occassion",
    "persistant",
    "posession",
    "prefered",
    "priviledge",
    "probablly",
    "publically",
    "realy",
    "recomend",
    "refered",
    "relevent",
    "religous",
    "remeber",
    "resistence",
    "responsable",
    "seperatly",
    "similiar",
    "succesful",
    "sucessful",
    "suprise",
    "tommorow",
    "truely",
    "unecessary",
    "usefull",
    "wierd",
    "writting",
}


class SpellChecker:
    def __init__(self, max_edit_distance: int = 2, prefix_length: int = 7):
        self.max_edit_distance = max_edit_distance
        self._sym = SymSpell(max_dictionary_edit_distance=max_edit_distance, prefix_length=prefix_length)
        base = resources.files("symspellpy")
        with base.joinpath("frequency_dictionary_en_82_765.txt").open("r", encoding="utf-8") as handle:
            self._sym.load_dictionary(handle, 0, 1)
        try:
            self._sym.load_bigram_dictionary(
                str(base.joinpath("frequency_bigramdictionary_en_243_342.txt")), 0, 2
            )
        except (OSError, ValueError):
            pass
        self.user_words: set[str] = set()
        self.base_words: set[str] = self._load_allowlist()

    @staticmethod
    def _load_allowlist() -> set[str]:
        path = resources.files("app.resources").joinpath("allowlist.txt")
        try:
            with path.open("r", encoding="utf-8") as handle:
                return {line.strip().lower() for line in handle if line.strip() and not line.startswith("#")}
        except (FileNotFoundError, OSError):
            return set()

    def add_word(self, word: str) -> None:
        word = word.strip().lower()
        if word:
            self.user_words.add(word)

    def remove_word(self, word: str) -> None:
        self.user_words.discard(word.strip().lower())

    def _is_known(self, word: str) -> bool:
        lower = word.lower()
        if lower in self.user_words or lower in self.base_words:
            return True
        if lower in COMMON_MISSPELLINGS:
            return False
        if lower in self._sym.words:
            return True
        return zipf_frequency(lower, "en") >= 2.5

    def _bigram(self, first: str, second: str) -> float:
        if not first or not second:
            return 0.0
        count = self._sym.bigrams.get(f"{first} {second}")
        if not count:
            return 0.0
        return math.log10(1 + count)

    def _score(self, candidate: str, distance: int, previous: str, following: str) -> float:
        score = 1.2 * zipf_frequency(candidate, "en")
        score += 0.45 * self._bigram(previous, candidate)
        score += 0.45 * self._bigram(candidate, following)
        score -= 2.0 * distance
        return score

    def _should_skip(self, token: Token) -> bool:
        if token.is_space or token.is_punct or token.like_num:
            return True
        if token.like_url or token.like_email:
            return True
        if not WORD_RE.match(token.text):
            return True
        if len(token.text) <= 2 and token.lower_ not in SHORT_WORDS:
            return True
        if token.ent_type_:
            return True
        if token.text[0].isupper() and not token.is_sent_start:
            return True
        return self._is_known(token.text)

    def check_document(self, doc: Doc) -> list[Issue]:
        words = [token for token in doc if not token.is_space]
        issues: list[Issue] = []
        for index, token in enumerate(words):
            if self._should_skip(token):
                continue
            previous = ""
            following = ""
            for back in range(index - 1, -1, -1):
                if words[back].is_alpha:
                    previous = words[back].lower_
                    break
            for forward in range(index + 1, len(words)):
                if words[forward].is_alpha:
                    following = words[forward].lower_
                    break
            suggestions = self._sym.lookup(
                token.lower_,
                Verbosity.CLOSEST,
                max_edit_distance=self.max_edit_distance,
                include_unknown=False,
            )
            ranked = []
            for item in suggestions:
                candidate = item.term
                if candidate.lower() == token.lower_:
                    continue
                ranked.append(
                    (self._score(candidate, item.distance, previous, following), candidate)
                )
            ranked.sort(key=lambda pair: pair[0], reverse=True)
            values = []
            for _, candidate in ranked:
                if candidate not in values:
                    values.append(candidate)
                if len(values) >= 4:
                    break
            if not values:
                continue
            start = token.idx
            end = token.idx + len(token.text)
            issues.append(
                Issue(
                    id=f"spell:{start}:{end}",
                    start=start,
                    end=end,
                    text=token.text,
                    type=IssueType.spelling,
                    severity=Severity.error,
                    message=f"Possible misspelling of '{token.text}'.",
                    suggestions=values,
                    rule_id="SPELL_UNKNOWN_WORD",
                    source=IssueSource.spellcheck,
                )
            )
        return issues
