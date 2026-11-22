from seo_analysis.analysis import fa_text
from seo_analysis.analysis.similarity import Settings, compare, prepare

PA = ("اتوماسیون اداری سامانه ای است که مکاتبات و اسناد و گردش کار سازمان را به صورت الکترونیکی مدیریت می کند. "
      "این سامانه ثبت نامه ها ارجاع و پیگیری آنها را ساده می کند و زمان پاسخگویی را کاهش می دهد. "
      "سازمان ها با استفاده از اتوماسیون اداری می توانند آرشیو الکترونیکی اسناد را ایجاد کنند و دسترسی کاربران را کنترل نمایند.")
PB = ("مدیریت ارتباط با مشتری ابزاری برای ثبت سرنخ ها و پیگیری فروش و ارتباط با مشتریان است. "
      "تیم فروش می تواند فرصت های فروش را در قیف فروش مشاهده کند و یادآور تماس بعدی را تنظیم نماید. "
      "گزارش های فروش و پیش بینی درآمد از امکانات مهم این سامانه است.")
PC = ("آرشیو الکترونیکی امکان نگهداری و جستجوی سریع هزاران سند را فراهم می کند و نسخه های قدیمی هر سند حفظ می شود. "
      "کاربران بر اساس سطح دسترسی خود اسناد را می بینند و ویرایش های هر سند ثبت و قابل بازگشت است.")
PD = ("مدیریت جلسات شامل دعوت اعضا و تنظیم دستور جلسه و ثبت مصوبات و پیگیری اجرای آنها است. "
      "مسئول هر مصوبه و مهلت انجام آن مشخص می شود و گزارش مصوبات معوق برای مدیران ارسال می گردد.")
PE = ("مدیریت پروژه با تابلو کانبان و نمودار گانت و تخصیص منابع به تیم کمک می کند تا پروژه ها در زمان مقرر تحویل شوند. "
      "گزارش پیشرفت هر پروژه و هزینه های آن در یک نگاه برای مدیر پروژه قابل مشاهده است.")


def item(url, text, title=None, h1="", ptype="blog"):
    return {"url": url, "title": title or url, "h1": h1, "text": text, "page_type": ptype}


def pairs(items, **kw):
    s = Settings(**kw)
    corpus = prepare(items, s, fa_text.load_stopwords())
    return {(p.url_a, p.url_b): p for p in compare(corpus)}


def test_short_page_contained_in_long_page_has_high_containment_but_low_jaccard():
    long = PA + " " + PB + " " + PC + " " + PD + " " + PE
    res = pairs([item("S", PA), item("L", long), item("U", PB + " " + PE)])
    p = res[("S", "L")]
    assert p.containment >= 0.9 and p.dup < 0.5
    assert "containment" in p.triggers and "near-duplicate" not in p.triggers
    assert p.short_page


def test_identical_pages_and_unrelated_pages():
    res = pairs([item("A", PA * 2), item("B", PA * 2), item("C", PB + PD + PE)])
    assert res[("A", "B")].dup == 1.0 and res[("A", "B")].containment == 1.0
    assert ("A", "C") not in res and ("B", "C") not in res


def test_half_space_and_arabic_letter_variants_do_not_hide_duplicates():
    a = PA * 2
    b = a.replace("نرم افزار", "نرم‌افزار").replace("می کند", "می‌کند").replace("ی", "ي").replace("ک", "ك")
    res = pairs([item("A", a), item("B", b), item("C", PB + PD)])
    assert res[("A", "B")].dup >= 0.99


def test_approved_variants_merge_joined_spelling():
    a = "این نرم افزار اداری برای سازمان ها ساخته شده است و نرم افزار پیوند همه کارها را انجام می دهد " * 4
    b = a.replace("نرم افزار", "نرمافزار")
    s = Settings()
    plain = {(p.url_a, p.url_b): p for p in compare(prepare([item("A", a), item("B", b)], s, fa_text.load_stopwords()))}
    v = {"نرمافزار": ("نرم", "افزار")}
    fixed = {(p.url_a, p.url_b): p for p in compare(prepare([item("A", a), item("B", b)], s, fa_text.load_stopwords(), v))}
    assert fixed[("A", "B")].dup > plain.get(("A", "B"), type("x", (), {"dup": 0})()).dup
    assert fixed[("A", "B")].dup >= 0.99


def test_pairs_are_explained_and_bounded():
    res = pairs([item("A", PA * 2, "اتوماسیون اداری چیست", "اتوماسیون اداری چیست؟"),
                 item("B", PA * 2 + PC, "اتوماسیون اداری چیست و چه کاربردی دارد", "اتوماسیون اداری چیست؟"),
                 item("C", PB + PD + PE)])
    p = res[("A", "B")]
    assert p.same_h1 and "same H1" in p.triggers and p.evidence >= 2
    assert p.shared_terms and len(p.shared_phrases) <= 3 and all(len(x) <= 70 for x in p.shared_phrases)
    assert any("اتوماسیون" in t for t in p.shared_terms)


def test_page_types_are_carried_and_empty_pages_do_not_crash():
    res = pairs([item("A", PA * 2, ptype="blog"), item("B", PA * 2, ptype="product"), item("E", ""), item("F", "کوتاه")])
    assert (res[("A", "B")].page_type_a, res[("A", "B")].page_type_b) == ("blog", "product")
    assert all("E" not in k and "F" not in k for k in res)
