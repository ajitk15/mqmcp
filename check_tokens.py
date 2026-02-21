
import os
from dotenv import load_dotenv
load_dotenv()

from mq_tools.prompts import MQ_SYSTEM_PROMPT
from mq_tools.schemas import TOOLS_OPENAI

print(f"System Prompt Chars: {len(MQ_SYSTEM_PROMPT)}")
print(f"System Prompt Approx Tokens: {len(MQ_SYSTEM_PROMPT) / 4}")

import json
tools_str = json.dumps(TOOLS_OPENAI)
print(f"Tools Schema Chars: {len(tools_str)}")
print(f"Tools Schema Approx Tokens: {len(tools_str) / 4}")

total_approx = (len(MQ_SYSTEM_PROMPT) + len(tools_str)) / 4
print(f"Total Approx Initial Tokens: {total_approx}")
