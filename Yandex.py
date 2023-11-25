import sys

import sf2_loader as sf2l
import fluidsynth
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QInputDialog
from PyQt5.Qt import Qt
from PyQt5.QtCore import QTimer
import time
from midiutil import MIDIFile
import sqlite3


# сделать name по умолчанию
class SoundFont():
    def __init__(self, file, driver='alsa'):
        soundfont = sf2l.sf2_loader(file)
        self.instruments = soundfont.all_instruments()
        soundfont.unload(0)

        self.fs = fluidsynth.Synth()
        self.fs.start(driver=driver)

        self.settings = fluidsynth.new_fluid_settings()
        self.synth = fluidsynth.new_fluid_synth(self.settings)

        self.file = file
        self.sfid = self.fs.sfload(file)
        self.bank = 0
        self.chan = 0
        self.preset = 0

        self.fs.program_select(0, self.sfid, self.bank, self.preset)

    def noteOn(self, key, vel):
        self.fs.noteon(self.chan, key, vel)

    def noteOff(self, key):
        self.fs.noteoff(self.chan, key)

    def allNotesOff(self):
        self.fs.all_notes_off(self.chan)

    def changeBank(self, bank=0):
        # if bank in self.instruments:
        self.fs.all_notes_off(self.chan)
        self.bank = bank
        self.fs.program_select(0, self.sfid, bank, self.preset)

    def changePreset(self, preset=0):
        # if preset in self.instruments[self.bank]:
        self.fs.all_notes_off(self.chan)
        self.preset = preset
        self.fs.program_select(0, self.sfid, self.bank, preset)

    def changeSoundFont(self, file):
        self.fs.sfunload(self.sfid)

        soundfont = sf2l.sf2_loader(file)
        self.instruments = soundfont.all_instruments()
        soundfont.unload(0)

        self.file = file
        self.sfid = self.fs.sfload(file)
        self.bank = 0
        self.chan = 0
        self.preset = 0

        self.fs.program_select(0, self.sfid, self.bank, self.preset)

    def getPresetName(self):
        return self.fs.channel_info(self.chan)[3]

    def getInstrumentList(self):
        return [f'{i} - {self.instruments[self.bank][i]}' for i in self.instruments[self.bank]]


class Master():
    def __init__(self):
        self.tempo = 120
        self.beats = 4
        self.tact = self.beats / (self.tempo / 60)
        self.octave = 4

        self.notes = {
            90: 0, 83: 1, 88: 2, 68: 3, 67: 4, 86: 5, 71: 6, 66: 7,
            72: 8, 78: 9, 74: 10, 77: 11, 44: 12, 76: 13, 46: 14, 59: 15,
            47: 16, 81: 12, 50: 13, 87: 14, 51: 15, 69: 16, 82: 17, 53: 18,
            84: 19, 54: 20, 89: 21, 55: 22, 85: 23, 73: 24, 57: 25, 79: 26,
            48: 27, 80: 28, 91: 29, 61: 30, 93: 31}

        self.recordMode = False
        self.playMode = False
        self.recordsStart = 0
        self.noteStartTime = [0] * 128
        self.share = 0

        self.mainInstrument = SoundFont('Mother 3 NEW.sf2')
        self.metronome = SoundFont('Mother 3 NEW.sf2')

        self.midiFile = MIDIFile(numTracks=1)

    def keyPress(self, key, vel):
        if key not in self.notes.keys():
            return

        pitch = self.notes[key] + 12 * self.octave
        self.mainInstrument.noteOn(pitch, vel)

        if not self.recordMode:
            return

        self.noteStartTime[pitch] = round((time.time() - self.recordsStart) / (self.tact / 32))

    def keyRelease(self, key, vel):
        if key not in self.notes.keys():
            return

        pitch = self.notes[key] + 12 * self.octave
        self.mainInstrument.noteOff(pitch)

        if not self.recordMode:
            return

        endTime = round((time.time() - self.recordsStart) / (self.tact / 32))
        startTime = self.noteStartTime[pitch] * 0.125
        duration = (endTime - self.noteStartTime[pitch]) * 0.125
        duration = 0.125 if duration == 0.0 else duration

        self.midiFile.addNote(0, 0, pitch, startTime, duration, vel)

    def click(self):
        if (self.share == 0):
            self.metronome.noteOn(78, 100)
            self.metronome.noteOff(78)
        else:
            self.metronome.noteOn(66, 100)
            self.metronome.noteOff(66)

        self.share = (self.share + 1) % self.beats

    def changeTempo(self, tempo):
        self.tempo = tempo
        self.tact = self.beats / (self.tempo / 60)


class MyWidget(QMainWindow):
    def __init__(self):
        super(MyWidget, self).__init__()
        uic.loadUi('untitled.ui', self)

        self.master = Master()

        self.recordButton.clicked.connect(self.record)
        self.saveButton.clicked.connect(self.save)
        self.playButton.clicked.connect(self.play)
        self.clearButton.clicked.connect(self.clear)

        self.slider.setValue(100)
        self.slider.setMinimum(0)
        self.slider.setMaximum(127)

        self.changeSoundButton.clicked.connect(self.SoundfondFile)

        self.plusOctaveButton.clicked.connect(self.plusOctave)
        self.minusOctaveButton.clicked.connect(self.minusOctave)

        self.tempoButton.clicked.connect(self.changeTempo)

        self.bankBox.addItems([str(i) for i in self.master.mainInstrument.instruments.keys()])
        self.bankBox.activated.connect(self.changeBank)
        self.bankBox.setEditable(False)

        self.box.addItems(self.master.mainInstrument.getInstrumentList())
        self.box.activated.connect(self.changePreset)
        self.box.setEditable(False)

        # self.presetBox.addItems([f'{i} {self.master.mainInstrument.instruments[self.master.mainInstrument.bank][i]}' for i in self.master.mainInstrument.instruments[self.master.mainInstrument.bank]])
        # self.presetBox.activated.connect(self.changePreset)

        self.clickTimer = QTimer()
        self.clickTimer.setInterval(int(self.master.tact * 1000 / self.master.beats))
        self.clickTimer.timeout.connect(self.master.click)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        self.master.keyPress(event.key(), self.slider.value())

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return
        self.master.keyRelease(event.key(), self.slider.value())

    def SoundfondFile(self):
        self.master.mainInstrument.allNotesOff()
        fName = QFileDialog.getOpenFileName(self, 'soundfond file', '')[0]
        self.master.mainInstrument.changeSoundFont(fName)
        self.box.clear()
        self.box.addItems(self.master.mainInstrument.getInstrumentList())
        self.changePreset()

    def changeBank(self):
        self.master.mainInstrument.allNotesOff()
        self.master.mainInstrument.changeBank(int(self.bankBox.currentText()))
        self.box.clear()
        self.box.addItems(self.master.mainInstrument.getInstrumentList())
        self.changePreset()
        self.setFocus()

    def changePreset(self):
        self.master.mainInstrument.allNotesOff()
        self.master.mainInstrument.changePreset(int(self.box.currentText().split(' ')[0]))
        self.setFocus()

    def plusOctave(self):
        if self.master.octave == 8:
            return
        self.master.mainInstrument.allNotesOff()
        self.master.octave += 1

    def minusOctave(self):
        if self.master.octave == 0:
            return
        self.master.mainInstrument.allNotesOff()
        self.master.octave -= 1

    def changeTempo(self):
        tempo, okPressed = QInputDialog.getInt(self, "change tempo", "tempo",
                                               self.master.tempo, 20, 300, 1)
        if not okPressed:
            return
        self.tempoButton.setText(str(tempo))
        self.master.changeTempo(tempo)
        self.clickTimer.setInterval(int(self.master.tact * 1000 / self.master.beats))

    def play(self):
        self.master.playMode = not self.master.playMode
        if self.master.playMode:
            self.playButton.setText('stop')
            # self.master.mainInstrument.fs.player_set_tempo(1, self.master.tempo)
            self.master.mainInstrument.fs.play_midi_file('test.mid')
        else:
            self.playButton.setText('play')
            self.master.mainInstrument.fs.play_midi_stop()

    def save(self):
        with open('test.mid', 'wb') as outputFile:
            self.master.midiFile.writeFile(outputFile)
        # names, ok_pressed = QInputDialog.getText(self, "Enter a name",
        #                                         "name of the melody")
        # if not ok_pressed:
        #     return
        # n = names + '.mid'
        # con = sqlite3.connect('melodies.db')
        # cur = con.cursor()
        # cur.execute("""INSERT INTO melody(name) VALUES(names)""")
        # con.commit()
        # nam = cur.execute("""SELECT * FROM melody""").fetchall()
        # print(nam)
        # con.close()

    def clear(self):
        self.master.midiFile = MIDIFile(numTracks=1)
        with open('test.mid', 'wb') as outputFile:
            self.master.midiFile.writeFile(outputFile)

    def record(self):
        self.master.recordMode = not self.master.recordMode
        if self.master.recordMode:
            self.recordButton.setText('stop')
            self.master.recordsStart = time.time()
            self.master.click()
            self.clickTimer.start()
        else:
            self.recordButton.setText('record')
            self.clickTimer.stop()
            self.master.share = 0


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyWidget()
    ex.show()
    sys.exit(app.exec())
