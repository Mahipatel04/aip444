# bad_code.py - Intentionally buggy code for testing the review tool
# This file contains security issues, performance problems, and bad practices

import sys
import os
import math
from typing import List

# BUG 1 (Security): Hardcoded API key - should be in environment variable
api_key = "sk-12345-abcde-secret-key"
database_password = "super_secret_password_123"

# BUG 2 (Performance): Inefficient function - O(n^2) nested loop
def find_duplicates(items: List[int]) -> List[int]:
    duplicates = []
    for i in range(len(items)):
        for j in range(len(items)):  # nested loop - very slow!
            if i != j and items[i] == items[j]:
                if items[i] not in duplicates:
                    duplicates.append(items[i])
    return duplicates

# BUG 3 (Maintainability): Bad variable names, wrong return type
def calculate_total(prices: List[float]) -> int:
    x = 0.0          # x is a terrible variable name
    for p in prices:  # p is also bad
        x += p
    return x          # returns float but type says int

# BUG 4 (Performance): Loads entire file into memory at once
def read_large_file(filename: str) -> List[str]:
    with open(filename, 'r') as f:
        all_lines = f.readlines()  # loads ENTIRE file into memory
    result = []
    for line in all_lines:
        if line.strip():
            result.append(line.strip())
    return result

# BUG 5 (Security): SQL injection vulnerability
def get_user(username: str) -> str:
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    return query  # dangerous! user input directly in SQL

# BUG 6 (Performance): Repeated expensive operation inside loop
def process_items(items: List[str]) -> List[str]:
    results = []
    for item in items:
        # len(items) is computed every iteration unnecessarily
        print(f"Processing {item} of {len(items)} total")
        results.append(item.upper())
    return results

# BUG 7 (Security): Hardcoded admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def main():
    print(f"Value of pi is: {math.pi}")

    total = calculate_total([10.50, 20.00, 5.25])
    print(f"Total: {total}")

    dupes = find_duplicates([1, 2, 3, 2, 4, 3, 5])
    print(f"Duplicates: {dupes}")

if __name__ == "__main__":
    main()