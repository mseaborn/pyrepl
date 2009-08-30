
# Copyright 2009 Mark Seaborn <mrs@mythic-beasts.com>
#
# Permission to use, copy, modify, and distribute this software and
# its documentation for any purpose is hereby granted without fee,
# provided that the above copyright notice appear in all copies and
# that both that copyright notice and this permission notice appear in
# supporting documentation.
#
# THE AUTHOR MICHAEL HUDSON DISCLAIMS ALL WARRANTIES WITH REGARD TO
# THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS, IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL,
# INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER
# RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF
# CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import time
import unittest

import gobject
import vte

import pyrepl.reader
import pyrepl.unix_console


class TestWrappingLongLines(unittest.TestCase):

    # Test that Reader wraps lines correctly before passing them to
    # UnixConsole.

    def make_example_reader(self):
        console = pyrepl.unix_console.UnixConsole()
        reader = pyrepl.reader.Reader(console)
        reader.ps1 = "foo$"
        reader.prepare()
        reader.restore() # Don't screw up terminal
        reader.console.width = 10
        reader.buffer = list("01234567890123456789")
        return reader

    def check_output(self, reader, lines):
        for line in lines:
            assert len(line) <= reader.console.width
        # Check cursor position consistency.
        for index, char in enumerate("".join(reader.buffer)):
            x, y = reader.pos2xy(index)
            self.assertEquals(lines[y][x], char)

    def test_wrapping(self):
        reader = self.make_example_reader()
        lines = reader.calc_screen()
        self.assertEquals(lines,
                          ["foo$01234\\", "567890123\\", "456789"])
        self.check_output(reader, lines)

    def test_wrapping_without_backslashes(self):
        reader = self.make_example_reader()
        reader.wrap_marker = ""
        lines = reader.calc_screen()
        self.assertEquals(lines,
                          ["foo$012345", "6789012345", "6789"])
        self.check_output(reader, lines)

    def test_wrapping_long_prompts(self):
        reader = self.make_example_reader()
        reader.wrap_marker = ""
        reader._ps1 = "0123456789foo$"
        lines = reader.calc_screen()
        self.assertEquals(lines,
                          ["0123456789",
                           "foo$012345", "6789012345", "6789"])
        self.check_output(reader, lines)

    def test_wrapping_status_message(self):
        reader = self.make_example_reader()
        reader.msg = "status1status2status3status4"
        lines = reader.calc_screen()
        self.assertEquals(lines,
                          ["foo$01234\\", "567890123\\", "456789",
                           "status1st\\", "atus2stat\\", "us3status\\", "4"])
        self.check_output(reader, lines)

        reader.msg_at_bottom = False
        lines = reader.calc_screen()
        self.assertEquals(lines,
                          ["status1st\\", "atus2stat\\", "us3status\\", "4",
                           "foo$01234\\", "567890123\\", "456789"])
        self.check_output(reader, lines)

        # There should be no empty line when the message exactly fills
        # the last line.
        reader.msg = "status1status2status3status"
        lines = reader.calc_screen()
        self.assertEquals(lines,
                          ["status1st\\", "atus2stat\\", "us3status",
                           "foo$01234\\", "567890123\\", "456789"])
        self.check_output(reader, lines)


class VTEConsole(pyrepl.unix_console.UnixConsole):

    def __init__(self, terminal):
        self._terminal = terminal
        pyrepl.unix_console.UnixConsole.__init__(self, f_in=None, term="xterm")

    # TODO: Don't use __ attributes in UnixConsole
    def flushoutput(self):
        for text, iscode in self._UnixConsole__buffer:
            self._terminal.feed(text.encode(self.encoding))
        del self._UnixConsole__buffer[:]

    def _update_size(self):
        pass


def get_vte_text(vte_terminal):
    # VTE updates the terminal in the event loop after a
    # non-configurable timeout, so we have to work around that.
    time.sleep(0.05)
    while gobject.main_context_default().iteration(False):
        pass
    return vte_terminal.get_text(lambda *args: True)


class TestUnixConsole(unittest.TestCase):

    def test_soft_newlines(self):
        terminal = vte.Terminal()
        terminal.set_size(10, 10)
        console = VTEConsole(terminal)
        console.width = 10
        console.height = 10
        console.prepare()

        # Check that a soft newline occurs.
        console.refresh(["0123456789",
                         "abcdefg"], (0, 0))
        self.assertEquals(get_vte_text(terminal),
                          "0123456789abcdefg" + "\n" * 9)

        # Check switching from soft newline to hard newline.
        # The chars "89" should disappear from the display.
        console.refresh(["01234567",
                         "abcdefg"], (0, 0))
        self.assertEquals(get_vte_text(terminal),
                          "01234567\nabcdefg" + "\n" * 9)

        # Test shortening the last line.
        console.refresh(["0123456789",
                         "abcd"], (0, 0))
        self.assertEquals(get_vte_text(terminal),
                          "0123456789abcd" + "\n" * 9)

    def test_soft_newlines_positioning(self):
        terminal = vte.Terminal()
        terminal.set_size(10, 10)
        console = VTEConsole(terminal)
        console.width = 10
        console.height = 10
        console.prepare()
        # Check that positioning is correct when starting from the
        # middle of the terminal.
        terminal.feed("\n\n")

        console.refresh(["012345678"], (0, 0))
        self.assertEquals(get_vte_text(terminal),
                          "\n\n012345678" + "\n" * 8)
        self.assertEquals(terminal.get_cursor_position(), (0, 2))

        # pyrepl's Reader produces empty lines.
        console.refresh(["0123456789", ""], (0, 0))
        self.assertEquals(get_vte_text(terminal),
                          "\n\n0123456789" + "\n" * 8)
        self.assertEquals(terminal.get_cursor_position(), (0, 2))

        console.refresh(["0123456789", "a"], (0, 0))
        self.assertEquals(get_vte_text(terminal),
                          "\n\n0123456789a" + "\n" * 7)
        self.assertEquals(terminal.get_cursor_position(), (0, 2))


if __name__ == "__main__":
    unittest.main()
