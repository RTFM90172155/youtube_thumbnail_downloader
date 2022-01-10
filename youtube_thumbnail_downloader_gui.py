# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.edge.webdriver import WebDriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from time import sleep
import threading
import requests
import sys
import os
import re

p_clip = re.compile(r"/watch\?[a-zA-Z0-9?&=_-]*?v=(?P<vid>[a-zA-Z0-9_-]+)&?")
p_playlist = re.compile(r"/(watch|playlist)\?[a-zA-Z0-9?&=_-]*?list=(?P<playlist>[a-zA-Z0-9_-]+)&?")
p_channel = re.compile(r"youtube\.com/(?P<channel>(c/|user/|channel/)?[\w%-]+)/?")
p_vid = re.compile(r"(/embed|youtu\.be)/(?P<vid>[a-zA-Z0-9_-]+)\??")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def work_relative_path(relative_path):
    work_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    return os.path.join(work_dir, relative_path)


class WebDriverLoader(QThread):

    loaded = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            options = Options()
            options.add_argument('window-size=1280,720')
            options.add_argument('headless')
            options.add_argument('disable-gpu')
            service = Service(EdgeChromiumDriverManager().install())
            driver = WebDriver(service=service, options=options)
            driver.implicitly_wait(5)
            self.loaded.emit(driver)
        except Exception:
            self.loaded.emit(None)


class ThumbnailDownloader(QThread):

    pBar_setRange = pyqtSignal(int, int)
    pBar_setValue = pyqtSignal(int)
    completed = pyqtSignal(int, int)

    def __init__(self, driver, url, save_dir, parent=None):
        super().__init__(parent)
        self.driver = driver
        self.url = url
        self.save_dir = save_dir
        self.flag = False

    def run(self):
        if p_clip.search(self.url):
            self.pBar_setRange.emit(0, 0)
            is_success = self.download_clip(self.url)
            self.pBar_setRange.emit(0, 1)
            self.pBar_setValue.emit(1)
            if is_success:
                self.completed.emit(1, 1)
            else:
                self.completed.emit(0, 1)
        else:
            self.download_list(self.url)

    def download_clip(self, url):
        thumbnails = ['maxresdefault', 'sddefault', 'hqdefault', 'mqdefault', 'default']
        vid = p_clip.search(url).group('vid')
        is_success = False
        for thumbnail in thumbnails:
            if self.flag:
                is_success = False
                break
            thumbnail_url = f'https://img.youtube.com/vi/{vid}/{thumbnail}.jpg'
            thumbnail_res = requests.get(thumbnail_url)
            if thumbnail_res.status_code == 200:
                file_name = f'{thumbnail}_{vid}.jpg'
                thumbnail_bin = thumbnail_res.content
                with open(os.path.join(self.save_dir, file_name), 'wb') as f:
                    f.write(thumbnail_bin)
                is_success = True
                break
        if is_success:
            print(f'Download: {file_name}')
        else:
            print(f'Failure: default_{vid}.jpg')
        return is_success

    def download_list(self, url):
        self.pBar_setRange.emit(0, 0)
        self.driver.get(url)

        elements = self.driver.find_elements(By.XPATH, '//*[@id="video-title"]')
        last_num = len(elements)
        reload_count = 0

        while reload_count < 3:
            if self.flag:
                print('(0/0) Success')
                self.completed.emit(0, 0)
                return
            print(f'{last_num} Loaded')
            self.driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            sleep(1)

            elements = self.driver.find_elements(By.XPATH, '//*[@id="video-title"]')
            current_num = len(elements)
            if last_num != current_num:
                last_num = current_num
                reload_count = 0
            else:
                reload_count += 1

        self.pBar_setRange.emit(0, last_num)
        self.pBar_setValue.emit(0)
        success_count = 0
        for i, element in enumerate(elements):
            if self.flag:
                print(f'({success_count}/{last_num}) Success')
                self.completed.emit(success_count, last_num)
                return
            video_url = element.get_attribute('href')
            print(f'({i+1}/{last_num}) ', end='')
            is_success = self.download_clip(video_url)
            if is_success:
                success_count += 1
            self.pBar_setValue.emit(i+1)

        sleep(1)
        print(f'({success_count}/{last_num}) Success')
        self.completed.emit(success_count, last_num)

    def stop(self):
        self.flag = True


class MainWindow(QWidget):

    download_stop = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.initUI()
        self.driver = None
        driver_loader = WebDriverLoader(self)
        driver_loader.loaded.connect(self.driver_load)
        driver_loader.start()

    def initUI(self):
        self.grid = QGridLayout()

        self.titleLb = QLabel('유튜브 썸네일 다운로더', self)
        self.titleLb.setAlignment(Qt.AlignCenter)
        titleLbFont = self.titleLb.font()
        titleLbFont.setPointSize(16)
        self.titleLb.setFont(titleLbFont)

        self.urlLb = QLabel('주소', self)
        self.urlLE = QLineEdit('', self)
        self.downBtn = QPushButton('시작', self)
        self.downBtn.clicked.connect(self.downBtnClicked)

        self.pBarLb = QLabel('진행률', self)
        self.pBar = QProgressBar(self)
        self.pBar.setFormat(r'%v/%m')
        self.pBar.setRange(0, 0)

        save_dir = work_relative_path('thumbnails')
        self.pathLb = QLabel('저장 경로', self)
        self.pathLE = QLineEdit(save_dir, self)
        self.selectBtn = QPushButton('선택', self)
        self.selectBtn.clicked.connect(self.selectBtnClicked)

        self.copyrightLb = QLabel('developed by @RTFM', self)
        self.copyrightLb.setAlignment(Qt.AlignBottom | Qt.AlignLeft)
        self.versionLb = QLabel('v1.0.0', self)
        self.versionLb.setAlignment(Qt.AlignBottom | Qt.AlignRight)

        self.grid.addWidget(self.titleLb, 0, 0, 1, 6)
        self.grid.addWidget(self.urlLb, 1, 0)
        self.grid.addWidget(self.urlLE, 1, 1, 1, 4)
        self.grid.addWidget(self.downBtn, 1, 5)
        self.grid.addWidget(self.pBarLb, 2, 0)
        self.grid.addWidget(self.pBar, 2, 1, 1, 5)
        self.grid.addWidget(self.pathLb, 3, 0)
        self.grid.addWidget(self.pathLE, 3, 1, 1, 4)
        self.grid.addWidget(self.selectBtn, 3, 5)
        self.grid.addWidget(self.copyrightLb, 4, 0, 1, 3)
        self.grid.addWidget(self.versionLb, 4, 3, 1, 3)

        for i in range(6):
            self.grid.setColumnMinimumWidth(i, 64)

        for i in range(5):
            self.grid.setRowMinimumHeight(i, 32)

        self.setLayout(self.grid)
        self.setWindowTitle('유튜브 썸네일 다운로더')
        self.setWindowIcon(QIcon(resource_path('icon.ico')))
        self.setFixedSize(self.sizeHint())
        self.center()
        self.show()

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def driver_load(self, driver):
        if driver:
            self.driver = driver
            self.pBar.setRange(0, 100)
            self.pBar.reset()
        else:
            QMessageBox.critical(self, '오류', '웹 드라이버를 불러오지 못했습니다.')
            QTimer.singleShot(0, self.close)

    def pBar_setRange(self, minimum, maximum):
        self.pBar.setRange(minimum, maximum)

    def pBar_setValue(self, value):
        self.pBar.setValue(value)

    def download_complete(self, success, total):
        QMessageBox.information(self, '다운로드 완료', f'{total}개의 영상에서 {success}개의 썸네일을 추출했습니다.')
        self.downBtn.setText('시작')
        self.pBar.setRange(0, 100)
        self.pBar.reset()

    def download_start(self, url, save_dir):
        self.downBtn.setText('중지')
        thumbnail_downloader = ThumbnailDownloader(self.driver, url, save_dir, self)
        thumbnail_downloader.pBar_setRange.connect(self.pBar_setRange)
        thumbnail_downloader.pBar_setValue.connect(self.pBar_setValue)
        thumbnail_downloader.completed.connect(self.download_complete)
        self.download_stop.connect(thumbnail_downloader.stop)
        thumbnail_downloader.start()

    def downBtnClicked(self):
        if not self.driver:
            QMessageBox.warning(self, '오류', '웹 드라이버를 불러오는 중입니다.\n잠시 후 다시 시도해 주세요.')
            return

        if self.downBtn.text() == '중지':
            self.download_stop.emit()
            return

        save_dir = self.pathLE.text()
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except Exception:
                QMessageBox.warning(self, '오류', '잘못된 경로입니다.')
                return

        url = self.urlLE.text()
        s_clip = p_clip.search(url)
        s_playlist = p_playlist.search(url)
        s_channel = p_channel.search(url)
        s_vid = p_vid.search(url)

        if s_clip:
            vid = s_clip.group('vid')
            if s_playlist:
                answer = QMessageBox.question(self, self.windowTitle(),
                    '이 비디오는 재생목록의 일부입니다.\n전체 재생목록을 다운로드하시겠습니까?')
                if answer == QMessageBox.Yes:
                    playlist = s_playlist.group('playlist')
                    playlist_url = f'https://youtube.com/playlist?list={playlist}'
                    self.download_start(playlist_url, save_dir)
                else:
                    video_url = f'https://www.youtube.com/watch?v={vid}'
                    self.download_start(video_url, save_dir)
            else:
                video_url = f'https://www.youtube.com/watch?v={vid}'
                self.download_start(video_url, save_dir)
        elif s_playlist:
            playlist = s_playlist.group('playlist')
            playlist_url = f'https://youtube.com/playlist?list={playlist}'
            self.download_start(playlist_url, save_dir)
        elif s_channel:
            channel = s_channel.group('channel')
            channel_url = f'https://youtube.com/{channel}/videos?sort=da'
            self.download_start(channel_url, save_dir)
        elif s_vid:
            vid = s_vid.group('vid')
            video_url = f'https://www.youtube.com/watch?v={vid}'
            self.download_start(video_url, save_dir)
        else:
            QMessageBox.warning(self, '오류', '잘못된 주소입니다.')
            return

    def selectBtnClicked(self):
        save_dir = str(QFileDialog.getExistingDirectory(self, '저장 경로 선택'))
        if save_dir:
            self.pathLE.setText(save_dir)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    exit_code = app.exec_()
    if window.driver:
        print('quit driver')
        window.driver.quit()
    print(f'exit: {exit_code}')
    sys.exit(exit_code)
