"""age_calculator — Strands-powered agent that computes a user's age in days.

Public API
----------
create_agent
    Factory function that builds and returns a configured ``strands.Agent``.

Example
-------
>>> from age_calculator import create_agent
>>> agent = create_agent()
>>> response = agent("My birthdate is 1990-05-15. How many days old am I?")
>>> print(response.message)
"""

from age_calculator.agent import create_agent

__all__: list[str] = ["create_agent"]
