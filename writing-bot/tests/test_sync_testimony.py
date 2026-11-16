"""Rules for which Drive files become corpus testimony (sync_testimony.py). No network.
    python -m unittest discover -s writing-bot/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync_testimony as s  # noqa: E402

LEG = "Drive/Legislative/State legislative/Housing - State Legislative/2025 Housing testimony/Testimony"
BODY = ("Testimony of the Hawaiʻi Appleseed Center for Law and Economic Justice\n"
        "Support for HB 431 – Relating to Housing\nSenate Committee on Ways and Means\n"
        "Aloha Chair Dela Cruz and members of the committee, thank you for the opportunity to testify. "
        + "Housing costs keep rising for working families across the islands every single year. " * 20)


class Judge(unittest.TestCase):
    def test_our_finished_testimony_is_kept(self):
        self.assertIsNone(s.judge("HB431 WAM", LEG, BODY))

    def test_rejections(self):
        cases = {
            ("Sample testimony HB431", LEG, BODY): "sample",
            ("HB431 WAM", LEG + "/Sample testimony", BODY): "sample",
            ("DRAFT HB431", LEG, BODY): "draft",
            ("HB2774 EDN (NOT SUBMITTED)", LEG, BODY): "draft",
            ("Estate Tax - Talking Points", LEG, BODY): "notes",
            ("HB1439_HD1_TESTIMONY_CPC_02-15-23_.pdf", LEG, BODY): "packet",
            ("HB431", LEG, "too short"): "short",
            ("HB431", LEG, BODY.replace("Hawaiʻi Appleseed Center for Law and Economic Justice", "Policing Project")): "Appleseed",
            ("Testimony", LEG, BODY.replace("HB 431", "the bill")): "bill",
            ("HB431", LEG, BODY + " [INSERT PERSONAL STORY]"): "placeholder",
            ("HB431", LEG, "DRAFT\n" + BODY): "draft",
        }
        for (name, path, text), word in cases.items():
            why = s.judge(name, path, text)
            self.assertIsNotNone(why, name)
            self.assertIn(word.lower(), why.lower(), (name, why))

    def test_signature_at_the_end_counts(self):
        body = BODY.replace("Testimony of the Hawaiʻi Appleseed Center for Law and Economic Justice\n", "")
        body = body.replace("Hawaiʻi Appleseed", "") + "\nMahalo,\nHawaiʻi Appleseed Center for Law and Economic Justice"
        self.assertIsNone(s.judge("HB431 WAM", LEG, body))


class Naming(unittest.TestCase):
    def test_file_name_follows_the_corpus_convention(self):
        self.assertEqual(s.file_name("HB431 WAM 3.28.25 (Supportive housing)", BODY, 2025),
                         "HB431_WAM_Supportive_housing_2025.txt")
        self.assertEqual(s.file_name("S.B. 960 HHS 1.29.25 (SNAP DHS staffing funds).pdf", "", 2025),
                         "SB960_HHS_SNAP_DHS_staffing_funds_2025.txt")
        self.assertTrue(s.file_name("Freedom to Walk", BODY, 2024).startswith("HB431_"))  # bill from the text

    def test_year_is_the_deepest_folder_year_then_the_hearing_date(self):
        self.assertEqual(s.year_of("Drive/Legislative/State legislative/Archives (2024 and prior)/2017", "", "2019-01-01"), 2017)
        self.assertEqual(s.year_of(LEG, "", "2026-01-01"), 2025)
        self.assertEqual(s.year_of("Drive/Litigation - LEJ/Legislative", "Hearing: February 3, 2022 at 9am", "2024-05-01"), 2022)
        self.assertEqual(s.year_of("Drive/Litigation - LEJ/Legislative", "", "2024-05-01T00:00:00Z"), 2024)

    def test_topic(self):
        self.assertEqual(s.topic_of(LEG, "HB431", BODY), "housing")
        self.assertEqual(s.topic_of("Drive/Litigation - LEJ/Cases/Closed/Foster Care Payments/Legislative Advocacy", "x", ""), "labor")
        self.assertEqual(s.topic_of("Drive/Litigation - LEJ/Legislative", "SB2110", "rental housing for tenants"), "housing")


class Text(unittest.TestCase):
    def test_okina(self):
        self.assertEqual(s.fix_okina("Hawai'i, O‘ahu, Kaua’i; don't, it's, Appleseed's"),  # okina-lint:ignore
                         "Hawaiʻi, Oʻahu, Kauaʻi; don't, it's, Appleseed's")

    def test_pdf_lines_rejoined(self):
        self.assertEqual(s.clean("We support\nthis bill.\n\nMahalo.", from_pdf=True), "We support this bill.\n\nMahalo.\n")

    def test_copy(self):
        a = s.words(BODY)
        self.assertTrue(s.is_copy(a, s.words(BODY.replace("Ways and Means", "Finance"))))
        self.assertFalse(s.is_copy(a, s.words("School meals feed keiki statewide; universal free school meals cost little.")))


if __name__ == "__main__":
    unittest.main()
