from openai import OpenAI
import os

# --------------------------------------------------
# Configuration
# --------------------------------------------------

ENDPOINT = os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"]
API_KEY = os.environ["AZURE_FOUNDRY_API_KEY"]

# Exact deployment name returned by Foundry
MODEL = "gpt-5-5-amr"


# --------------------------------------------------
# Create client
# --------------------------------------------------

client = OpenAI(
    base_url=ENDPOINT.rstrip("/") + "/openai/v1/",
    api_key=API_KEY,
)


# --------------------------------------------------
# Test request
# --------------------------------------------------

try:
    response = client.responses.create(
        model=MODEL,
        input="What is 2 + 2? Answer with only the number."
    )

    print("SUCCESS!")
    print()

    print("Model deployment:")
    print(MODEL)

    print()

    print("Output:")
    print(response.output_text)

    print()

    print("Token usage:")
    print("Input tokens: ", response.usage.input_tokens)
    print("Output tokens:", response.usage.output_tokens)
    print("Total tokens: ", response.usage.total_tokens)

except Exception as e:
    print("REQUEST FAILED")
    print(type(e).__name__)
    print(e)