import unittest

from lottery import parse_recent_page, parse_sample_html, result_by_period


RECENT_HTML = """
<table>
  <tbody>
    <tr class="latest">
      <td class="period">115000051</td>
      <td class="date">2026-05-08</td>
      <td class="day">五</td>
      <td class="numbers">
        <div class="number-row">
          <a class="number-ball">10</a>
          <a class="number-ball">18</a>
          <a class="number-ball">25</a>
          <a class="number-ball">28</a>
          <a class="number-ball">39</a>
          <a class="number-ball">43</a>
        </div>
      </td>
      <td class="special">
        <a class="number-ball special">48</a>
      </td>
    </tr>
  </tbody>
</table>
"""


class LottoParserTests(unittest.TestCase):
    def test_basic_sample_html(self):
        result = parse_sample_html()
        self.assertEqual(result.period, "115000049")
        self.assertEqual(result.date, "115/05/01")
        self.assertEqual(result.numbers, ["07", "22", "27", "35", "43", "48"])
        self.assertEqual(result.special, "45")

    def test_parse_recent_page(self):
        results = parse_recent_page(RECENT_HTML)
        self.assertEqual(results[0].period, "115000051")
        self.assertEqual(results[0].date, "2026-05-08")
        self.assertEqual(results[0].numbers, ["10", "18", "25", "28", "39", "43"])
        self.assertEqual(results[0].special, "48")


if __name__ == "__main__":
    unittest.main()
