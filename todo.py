#!/usr/bin/env python3
"""Todo List // Blackjack Edition. Чистый stdlib, Python 3.14."""
import curses
import locale
import random
import sqlite3
from datetime import datetime
from pathlib import Path

locale.setlocale(locale.LC_ALL, "")

DB_DIR = Path(os.environ.get("TODO_DB_DIR", Path(__file__).resolve().parent))
DB_PATH = DB_DIR / "tasks.db"


def init_db() -> sqlite3.Connection:
    # DB_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            title    TEXT    NOT NULL,
            priority INTEGER NOT NULL DEFAULT 2,
            done     INTEGER NOT NULL DEFAULT 0,
            created  TEXT    NOT NULL
        )
    """)
    con.commit()
    return con


class TodoApp:
    def __init__(self, stdscr, con):
        self.stdscr = stdscr
        self.con = con
        self.cursor = 0
        self.offset = 0
        self.mode = "list"           # list | input | blackjack
        self.input_buf = ""
        self.input_priority = 2
        self.message = ""
        self.bj = None
        self._init_colors()

    def _init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN,    -1)
        curses.init_pair(2, curses.COLOR_GREEN,   -1)
        curses.init_pair(3, curses.COLOR_YELLOW,  -1)
        curses.init_pair(4, curses.COLOR_RED,     -1)
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)
        curses.init_pair(6, curses.COLOR_BLACK,   curses.COLOR_CYAN)

    # ---------- data ----------
    def fetch(self):
        return self.con.execute(
            "SELECT id, title, priority, done FROM tasks "
            "ORDER BY done ASC, priority DESC, id ASC"
        ).fetchall()

    def current_id(self):
        rows = self.fetch()
        return rows[self.cursor][0] if rows and self.cursor < len(rows) else None

    # ---------- main loop ----------
    def run(self):
        curses.curs_set(0)
        self.stdscr.keypad(True)
        while True:
            self.draw()
            if not self.handle(self.stdscr.getch()):
                break

    # ---------- rendering ----------
    def draw(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        title = " ◤ TODO // BLACKJACK EDITION ◢ "
        self.stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        self.stdscr.addstr(0, max(0, (w - len(title)) // 2), title[: w - 1])
        self.stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

        if self.mode == "blackjack":
            self.draw_blackjack(h, w)
        else:
            self.draw_list(h, w)

        if self.message:
            self.stdscr.addstr(h - 2, 2, self.message[: w - 4])

        hint = (" [a]dd  [space]toggle  [d]elete  [p]riority  "
                "[↑↓]move  [b]lackjack  [q]uit ")
        self.stdscr.attron(curses.color_pair(6))
        self.stdscr.addstr(h - 1, 0, hint.ljust(w - 1)[: w - 1])
        self.stdscr.attroff(curses.color_pair(6))
        self.stdscr.refresh()

    def draw_list(self, h, w):
        rows = self.fetch()
        visible = h - 5
        if self.cursor < self.offset:
            self.offset = self.cursor
        if self.cursor >= self.offset + visible:
            self.offset = self.cursor - visible + 1

        if not rows:
            self.stdscr.addstr(2, 2, "Пока пусто. Жми 'a' чтобы добавить задачу.",
                               curses.A_DIM)
        else:
            for i, (_, title, prio, done) in enumerate(
                    rows[self.offset:self.offset + visible]):
                idx = self.offset + i
                y = i + 2
                marker = "▸" if idx == self.cursor else " "
                check = "[x]" if done else "[ ]"
                prio_str = {1: "LOW ", 2: "MED ", 3: "HIGH"}.get(prio, "MED ")

                if idx == self.cursor:
                    attrs = curses.color_pair(6) | curses.A_BOLD
                elif done:
                    attrs = curses.color_pair(2) | curses.A_DIM
                elif prio == 3:
                    attrs = curses.color_pair(4) | curses.A_BOLD
                elif prio == 1:
                    attrs = curses.color_pair(3)
                else:
                    attrs = curses.color_pair(0)

                line = f"{marker} {check} {prio_str} {title}"
                self.stdscr.addstr(y, 0, line[: w - 1].ljust(w - 1), attrs)

        if self.mode == "input":
            prompt = f"Новая задача [P{self.input_priority}] ←→: "
            self.stdscr.addstr(h - 3, 2, prompt,
                               curses.color_pair(5) | curses.A_BOLD)
            self.stdscr.addstr(h - 3, 2 + len(prompt),
                               self.input_buf[: w - len(prompt) - 3])
        else:
            done_n = sum(1 for r in rows if r[3])
            self.stdscr.addstr(h - 3, 2,
                               f"Всего: {len(rows)}  Выполнено: {done_n}",
                               curses.A_DIM)

    def draw_blackjack(self, h, w):
        bj = self.bj
        self.stdscr.addstr(2, 2, "🎴 BLACKJACK 21",
                           curses.color_pair(5) | curses.A_BOLD)
        if bj["revealed"]:
            self.stdscr.addstr(4, 2,
                f"Дилер: {self.card_str(bj['dealer'])}  "
                f"({self.hand_value(bj['dealer'])})")
        else:
            self.stdscr.addstr(4, 2,
                f"Дилер: {bj['dealer'][0]} [?]")
        self.stdscr.addstr(6, 2,
            f"Вы:    {self.card_str(bj['player'])}  "
            f"({self.hand_value(bj['player'])})")

        if bj["state"] == "player":
            self.stdscr.addstr(h - 3, 2, "[h]it  [s]tand  [Esc]выход",
                               curses.A_BOLD)
        else:
            self.stdscr.addstr(h - 3, 2,
                f"{bj['result']}   [Enter]—ещё, [Esc]—выход",
                curses.A_BOLD)

    # ---------- blackjack ----------
    def new_blackjack(self):
        self.bj = {
            "player": [self.deal_card(), self.deal_card()],
            "dealer": [self.deal_card(), self.deal_card()],
            "revealed": False,
            "state": "player",
            "result": "",
        }
        if self.hand_value(self.bj["player"]) == 21:
            self.bj["revealed"] = True
            self.bj["state"] = "over"
            self.bj["result"] = "BLACKJACK! 🎉"

    @staticmethod
    def deal_card() -> str:
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        return random.choice(ranks) + random.choice(["♠", "♥", "♦", "♣"])

    @staticmethod
    def card_str(cards) -> str:
        return " ".join(cards)

    @staticmethod
    def hand_value(cards) -> int:
        total, aces = 0, 0
        for c in cards:
            r = c[:-1]
            if r in ("J", "Q", "K"):
                total += 10
            elif r == "A":
                aces += 1
                total += 11
            else:
                total += int(r)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def handle_blackjack(self, key) -> bool:
        if key == 27:
            self.mode = "list"
            self.bj = None
            return True
        bj = self.bj
        if bj["state"] == "over":
            if key in (10, 13, curses.KEY_ENTER):
                self.new_blackjack()
            return True
        if key == ord("h"):
            bj["player"].append(self.deal_card())
            if self.hand_value(bj["player"]) > 21:
                bj["state"] = "over"
                bj["revealed"] = True
                bj["result"] = "Перебор! Дилер выиграл 💀"
        elif key == ord("s"):
            bj["revealed"] = True
            while self.hand_value(bj["dealer"]) < 17:
                bj["dealer"].append(self.deal_card())
            pv, dv = (self.hand_value(bj["player"]),
                      self.hand_value(bj["dealer"]))
            if dv > 21:
                bj["result"] = f"Дилер перебрал ({dv})! Ты выиграл 🎉"
            elif pv > dv:
                bj["result"] = f"Ты выиграл! {pv} > {dv} 🎉"
            elif pv < dv:
                bj["result"] = f"Дилер выиграл. {pv} < {dv} 💀"
            else:
                bj["result"] = f"Ничья. {pv} = {dv} 🤝"
            bj["state"] = "over"
        return True

    # ---------- list keys ----------
    def handle(self, key) -> bool:
        if self.mode == "blackjack":
            return self.handle_blackjack(key)
        if self.mode == "input":
            return self.handle_input(key)

        if key in (ord("q"), 27):
            return False
        if key == ord("a"):
            self.mode, self.input_buf = "input", ""
        elif key == ord("b"):
            self.mode = "blackjack"
            self.new_blackjack()
        elif key in (curses.KEY_UP, ord("k")):
            self.cursor = max(0, self.cursor - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            self.cursor = min(max(0, len(self.fetch()) - 1), self.cursor + 1)
        elif key == ord(" "):
            self.toggle_current()
        elif key == ord("d"):
            self.delete_current()
        elif key == ord("p"):
            self.cycle_priority()
        return True

    def handle_input(self, key) -> bool:
        if key == 27:
            self.mode = "list"
            return True
        if key in (10, 13, curses.KEY_ENTER):
            title = self.input_buf.strip()
            if title:
                self.con.execute(
                    "INSERT INTO tasks (title, priority, done, created) "
                    "VALUES (?, ?, 0, ?)",
                    (title, self.input_priority,
                     datetime.now().isoformat(timespec="seconds")),
                )
                self.con.commit()
                self.message = f"Добавлено: {title}"
            self.mode = "list"
            return True
        if key in (curses.KEY_BACKSPACE, 127, 8):
            self.input_buf = self.input_buf[:-1]
        elif key == curses.KEY_LEFT:
            self.input_priority = max(1, self.input_priority - 1)
        elif key == curses.KEY_RIGHT:
            self.input_priority = min(3, self.input_priority + 1)
        elif 32 <= key < 127:
            self.input_buf += chr(key)
        return True

    # ---------- mutations ----------
    def toggle_current(self):
        if (tid := self.current_id()) is not None:
            self.con.execute("UPDATE tasks SET done = 1 - done WHERE id = ?", (tid,))
            self.con.commit()

    def delete_current(self):
        if (tid := self.current_id()) is not None:
            self.con.execute("DELETE FROM tasks WHERE id = ?", (tid,))
            self.con.commit()
            self.cursor = min(self.cursor, max(0, len(self.fetch()) - 1))
            self.message = "Удалено."

    def cycle_priority(self):
        if (tid := self.current_id()) is None:
            return
        row = self.con.execute("SELECT priority FROM tasks WHERE id = ?",
                               (tid,)).fetchone()
        if row:
            new_p = {1: 2, 2: 3, 3: 1}[row[0]]
            self.con.execute("UPDATE tasks SET priority = ? WHERE id = ?",
                             (new_p, tid))
            self.con.commit()


def main(stdscr):
    con = init_db()
    try:
        TodoApp(stdscr, con).run()
    finally:
        con.close()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass