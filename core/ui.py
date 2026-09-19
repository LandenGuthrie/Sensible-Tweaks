"""Minimal terminal UI helpers."""
import os

WIDTH = 62


def clear() -> None:
    os.system("cls")


def header(title: str) -> None:
    line = "=" * WIDTH
    print()
    print(f"  {line}")
    print(f"   {title.center(WIDTH - 2)}")
    print(f"  {line}")
    print()


def prompt(msg: str = "Choose: ") -> str:
    return input(f"   {msg}").strip()


def pause(msg: str = "Press Enter to continue...") -> None:
    input(f"\n   {msg}")


def ok(msg: str) -> None:
    print(f"   [OK]  {msg}")


def err(msg: str) -> None:
    print(f"   [ERR] {msg}")


def info(msg: str) -> None:
    print(f"   [--]  {msg}")