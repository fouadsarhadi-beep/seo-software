from seo_analysis.analysis import fa_text as fa


def test_arabic_letters_become_persian():
    assert fa.normalize("كتاب ي") == "کتاب ی"


def test_digits_unified():
    assert fa.normalize("۱۲۳ ٤٥٦") == "123 456"


def test_half_space_equals_space():
    assert fa.tokenize("نرم‌افزار") == fa.tokenize("نرم افزار") == ["نرم", "افزار"]


def test_diacritics_and_tatweel_removed():
    assert fa.tokenize("كِتَابـــ") == ["کتاب"]


def test_presentation_forms_folded():
    assert fa.normalize("\ufefb") == "لا"


def test_invisible_marks_removed():
    assert fa.tokenize("سامانه\u200f\u200e") == ["سامانه"]


def test_variants_map_splits_joined_word(tmp_path):
    f = tmp_path / "v.json"
    f.write_text('{"نرمافزار": "نرم افزار"}', encoding="utf-8")
    v = fa.load_variants(f)
    assert fa.tokenize("نرمافزار اداری", v) == ["نرم", "افزار", "اداری"]


def test_stopwords_contain_function_words_not_domain_words():
    s = fa.load_stopwords()
    assert "و" in s and "تان" in s
    assert "سازمان" not in s and "سامانه" not in s and "اتوماسیون" not in s


def test_persian_ratio():
    assert fa.persian_ratio("سلام دنیا") == 1.0
    assert fa.persian_ratio("hello") == 0.0
