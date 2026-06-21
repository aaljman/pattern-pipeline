from django.test import SimpleTestCase

from datasets.services.regex_generation import TemplateRegexProvider
from datasets.services.transformations import compile_pattern


BENCHMARK_CASES = [
    ("find email addresses", "ada@example.com", "ada at example dot com"),
    ("redact every email", "first.last+tag@sub.example.org", "first.last.example.org"),
    ("mask e-mail values", "user_2@company.co", "user_2@company"),
    ("detect contact emails", "support@service.io", "support.service.io"),
    ("replace an email address", "a-b@example.travel", "a-b@example"),
    ("locate email identifiers", "hello.world@example.net", "hello world@example"),
    ("remove emails from notes", "x%tag@example.com", "x%tag example.com"),
    ("find e-mail contact details", "team+au@example.com.au", "team+au@"),
    ("find Australian phone numbers", "0412 345 678", "12345"),
    ("mask mobile numbers", "+61 412 345 678", "+1 412 345 678"),
    ("redact phone values", "02 9876 5432", "00 9876 5432"),
    ("detect mobile contacts", "0478123456", "1478123456"),
    ("replace phone details", "+61412345678", "+61912345678"),
    ("locate phone numbers", "03-9123-4567", "03-9123-456"),
    ("remove mobile contacts", "0499 111 222", "0499 111 22"),
    ("find phone contact details", "07 3123 4567", "09 3123 4567"),
    ("find URL values", "https://example.com/path", "example dot com"),
    ("redact website links", "http://example.org", "ftp://example.org"),
    ("mask web address fields", "https://sub.example.com?a=1", "sub.example.com"),
    ("detect URLs in notes", "https://example.io/docs#one", "mailto:user@example.io"),
    ("replace website addresses", "HTTP://EXAMPLE.COM", "www dot example dot com"),
    ("locate URL links", "https://example.com/a-b", "example.com/a-b"),
    ("remove web address values", "http://127.0.0.1/test", "127.0.0.1/test"),
    ("find website references", "https://example.travel", "example.travel"),
    ("find IPv4 addresses", "192.168.1.10", "999.1.1.1"),
    ("redact IP address values", "10.0.0.1", "10.0.0.999"),
    ("mask ipv4 identifiers", "255.255.255.255", "256.255.255.255"),
    ("detect ip addresses", "172.16.0.4", "172.16.0"),
    ("replace IPv4 values", "8.8.8.8", "8.8.8.888"),
    ("locate IP address strings", "127.0.0.1", "127.0.0.-1"),
    ("remove ipv4 details", "1.2.3.4", "1.2.3"),
    ("find IP addresses in logs", "203.0.113.42", "203.0.113.420"),
]


class BuiltInRegexBenchmarkTests(SimpleTestCase):
    def test_common_pattern_library_scores_perfectly_on_32_intents(self):
        provider = TemplateRegexProvider()
        true_positives = 0
        false_positives = 0
        compiled_cases = 0

        for instruction, positive, negative in BENCHMARK_CASES:
            proposal = provider.generate(instruction, ["sample"])
            compiled = compile_pattern(proposal.pattern, proposal.flags)
            compiled_cases += 1
            true_positives += int(compiled.search(positive) is not None)
            false_positives += int(compiled.search(negative) is not None)

        compile_rate = compiled_cases / len(BENCHMARK_CASES)
        recall = true_positives / len(BENCHMARK_CASES)
        precision = true_positives / (true_positives + false_positives)

        self.assertEqual(compile_rate, 1.0)
        self.assertEqual(recall, 1.0)
        self.assertEqual(precision, 1.0)
