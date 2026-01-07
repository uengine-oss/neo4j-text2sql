from app.react.generators.explain_analysis_generator import ExplainAnalysisLLMResponse


def test_explain_analysis_from_xml_repairs_text_fields_with_angle_brackets() -> None:
    # '<schema>' in free text and '<' operators inside <sql>/<reason> would normally break XML parsing.
    xml_text = """<validation_plan>
  <risk_analysis>
    <summary>Need a <schema> tag and 2 < 3 comparisons can appear</summary>
  </risk_analysis>
  <queries>
    <query id="1">
      <reason>Verify selectivity where 2 < 3 is present in predicates</reason>
      <sql>SELECT 1 WHERE 2 < 3;</sql>
    </query>
  </queries>
</validation_plan>
"""

    parsed = ExplainAnalysisLLMResponse.from_xml(xml_text)
    assert "<schema>" in parsed.risk_summary
    assert "2 < 3" in parsed.risk_summary
    assert len(parsed.validation_queries) == 1
    assert "2 < 3" in parsed.validation_queries[0].reason
    assert "2 < 3" in parsed.validation_queries[0].sql


