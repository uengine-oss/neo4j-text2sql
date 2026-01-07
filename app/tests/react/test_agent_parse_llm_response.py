from app.react.agent import ReactAgent


def test_parse_llm_response_trims_trailing_junk_after_output() -> None:
    agent = ReactAgent.__new__(ReactAgent)

    response = """<output>
  <reasoning>ok</reasoning>
  <collected_metadata>
    <identified_tables/>
    <identified_columns/>
    <identified_values/>
    <identified_relationships/>
    <identified_constraints/>
  </collected_metadata>
  <partial_sql><![CDATA[SELECT 1]]></partial_sql>
  <sql_completeness_check>
    <is_complete>false</is_complete>
    <missing_info>need schema</missing_info>
    <confidence_level>low</confidence_level>
  </sql_completeness_check>
  <tool_call>
    <tool_name>search_tables</tool_name>
    <parameters>["pressure"]</parameters>
  </tool_call>
</output>

<tool_call name="search_tables">["pressure"]</tool_call>```
"""

    step = agent._parse_llm_response(
        response,
        iteration=1,
        react_run_id="test_run",
        state_snapshot={"case": "trailing_junk"},
    )

    assert step.tool_call.name == "search_tables"
    assert step.tool_call.parsed_parameters == {"keywords": ["pressure"]}
    assert "<collected_metadata" in step.metadata_xml


def test_parse_llm_response_unwraps_nested_output() -> None:
    agent = ReactAgent.__new__(ReactAgent)

    nested = """<output>
  <output>
    <reasoning>ok</reasoning>
    <collected_metadata>
      <identified_tables/>
      <identified_columns/>
      <identified_values/>
      <identified_relationships/>
      <identified_constraints/>
    </collected_metadata>
    <partial_sql><![CDATA[SELECT 1]]></partial_sql>
    <sql_completeness_check>
      <is_complete>false</is_complete>
      <missing_info>need schema</missing_info>
      <confidence_level>low</confidence_level>
    </sql_completeness_check>
    <tool_call>
      <tool_name>search_tables</tool_name>
      <parameters>["plant"]</parameters>
    </tool_call>
  </output>
</output>
"""

    step = agent._parse_llm_response(
        nested,
        iteration=1,
        react_run_id="test_run",
        state_snapshot={"case": "nested_output"},
    )

    assert step.tool_call.name == "search_tables"
    assert step.tool_call.parsed_parameters == {"keywords": ["plant"]}
    assert "<collected_metadata" in step.metadata_xml


def test_parse_llm_response_repairs_note_text_with_angle_brackets() -> None:
    agent = ReactAgent.__new__(ReactAgent)

    # <schema> inside <note> would normally break XML parsing (mismatched tags).
    response = """<output>
  <reasoning>ok</reasoning>
  <collected_metadata>
    <identified_tables/>
    <identified_columns/>
    <identified_values/>
    <identified_relationships/>
    <identified_constraints/>
  </collected_metadata>
  <note>Include a <schema> tag in each entry</note>
  <partial_sql><![CDATA[SELECT 1]]></partial_sql>
  <sql_completeness_check>
    <is_complete>false</is_complete>
    <missing_info>need schema</missing_info>
    <confidence_level>low</confidence_level>
  </sql_completeness_check>
  <tool_call>
    <tool_name>search_tables</tool_name>
    <parameters>["pressure"]</parameters>
  </tool_call>
</output>
"""

    step = agent._parse_llm_response(
        response,
        iteration=1,
        react_run_id="test_run",
        state_snapshot={"case": "note_with_angle_brackets"},
    )

    assert step.tool_call.name == "search_tables"
    assert step.tool_call.parsed_parameters == {"keywords": ["pressure"]}


def test_parse_llm_response_repairs_reasoning_and_missing_info_with_angle_brackets() -> None:
    agent = ReactAgent.__new__(ReactAgent)

    response = """<output>
  <reasoning>Need a <schema> tag, and 2 < 3 comparisons may appear</reasoning>
  <collected_metadata>
    <identified_tables/>
    <identified_columns/>
    <identified_values/>
    <identified_relationships/>
    <identified_constraints/>
  </collected_metadata>
  <partial_sql><![CDATA[SELECT 1]]></partial_sql>
  <sql_completeness_check>
    <is_complete>false</is_complete>
    <missing_info>Example: 2 < 3 means 'less than'</missing_info>
    <confidence_level>low</confidence_level>
  </sql_completeness_check>
  <tool_call>
    <tool_name>search_tables</tool_name>
    <parameters>["plant"]</parameters>
  </tool_call>
</output>
"""

    step = agent._parse_llm_response(
        response,
        iteration=1,
        react_run_id="test_run",
        state_snapshot={"case": "reasoning_missing_info_angle_brackets"},
    )

    assert "<schema>" in step.reasoning
    assert "2 < 3" in step.reasoning
    assert "2 < 3" in step.sql_completeness.missing_info


def test_parse_llm_response_repairs_parameters_text_only_sql_with_lt_operator() -> None:
    agent = ReactAgent.__new__(ReactAgent)

    response = """<output>
  <reasoning>ok</reasoning>
  <collected_metadata>
    <identified_tables/>
    <identified_columns/>
    <identified_values/>
    <identified_relationships/>
    <identified_constraints/>
  </collected_metadata>
  <partial_sql><![CDATA[SELECT 1]]></partial_sql>
  <sql_completeness_check>
    <is_complete>false</is_complete>
    <missing_info>need schema</missing_info>
    <confidence_level>low</confidence_level>
  </sql_completeness_check>
  <tool_call>
    <tool_name>execute_sql_preview</tool_name>
    <parameters>SELECT 1 WHERE 2 < 3</parameters>
  </tool_call>
</output>
"""

    step = agent._parse_llm_response(
        response,
        iteration=1,
        react_run_id="test_run",
        state_snapshot={"case": "parameters_text_only_sql_with_lt"},
    )

    assert step.tool_call.name == "execute_sql_preview"
    assert step.tool_call.parsed_parameters == {"sql": "SELECT 1 WHERE 2 < 3"}


def test_parse_llm_response_does_not_wrap_parameters_with_child_tags() -> None:
    agent = ReactAgent.__new__(ReactAgent)

    response = """<output>
  <reasoning>ok</reasoning>
  <collected_metadata>
    <identified_tables/>
    <identified_columns/>
    <identified_values/>
    <identified_relationships/>
    <identified_constraints/>
  </collected_metadata>
  <partial_sql><![CDATA[SELECT 1]]></partial_sql>
  <sql_completeness_check>
    <is_complete>false</is_complete>
    <missing_info>need schema</missing_info>
    <confidence_level>low</confidence_level>
  </sql_completeness_check>
  <tool_call>
    <tool_name>search_column_values</tool_name>
    <parameters>
      <schema>public</schema>
      <table>plants</table>
      <column>name</column>
      <search_keywords>["청주시"]</search_keywords>
    </parameters>
  </tool_call>
</output>
"""

    step = agent._parse_llm_response(
        response,
        iteration=1,
        react_run_id="test_run",
        state_snapshot={"case": "parameters_child_tags"},
    )

    assert step.tool_call.name == "search_column_values"
    assert step.tool_call.parsed_parameters == {
        "schema": "public",
        "table": "plants",
        "column": "name",
        "search_keywords": ["청주시"],
    }



