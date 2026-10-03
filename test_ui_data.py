from src.ui.research_context import (
    build_company_context
)


data = build_company_context("AAPL")


print("\n===== UI DATA TEST =====\n")

for key, value in data.items():
    print(f"{key:<22} {value}")