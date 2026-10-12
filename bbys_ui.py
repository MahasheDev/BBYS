"""BBYS Qt UI: live acrylic and rounded geometry from design.png."""
import ctypes
import json
import os
from pathlib import Path
import queue
import sys
import threading
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QLinearGradient,QPixmap,QIcon,QShortcut,QKeySequence,QRegion
from PySide6.QtWidgets import (QApplication,QWidget,QLabel,QVBoxLayout,QHBoxLayout,QGridLayout,QScrollArea,QLineEdit,QPlainTextEdit,QFileDialog,QMessageBox,QDialog,QSizePolicy,QAbstractButton)
import bbys_registry as reg
from bbys_controller import Controller
from bbys_system import WindowsBackend,broadcast_environment
import bbys_temp
from bbys_apps import uninstall_lighting
from bbys_glass import (TEXT,MUTED,BLUE,GREEN,YELLOW,SIDEBAR_WIDTH,WINDOW_RADIUS,GlassButton,GlassCard,Switch,NavButton,Icon,STYLE,font,enable_native_glass,clip_native_window)

APP_DIR=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
ASSETS=Path(getattr(sys,'_MEIPASS',APP_DIR))
NAV=[('Система','system'),('Проводник','folder'),('Внешний вид','palette'),('Конфиденциальность','shield'),('Приложения','apps'),('Автозагрузка','play'),('Сеть','globe'),('Дополнительно','sliders')]
EXTRA=['Папки','TEMP','PATH','Утилиты']
FOLDERS=[('Рабочий стол','Desktop','system'),('Документы','Personal','file'),('Загрузки','{374DE290-123F-4565-9164-39C4925E467B}','download'),('Музыка','My Music','music'),('Изображения','My Pictures','image'),('Видео','My Video','video')]
SECTIONS={
 'Система':[
  ('Настройка Windows','system',['simple_optimization','extended_optimization','game_priority']),
  ('Службы и обновления','sliders',['disable_printing','disable_indexing','disable_driver_auto_update','optimize_service_isolation']),
  ('Клавиатура и мышь','keyboard',['disable_mouse_acceleration','disable_accessibility_keyboard_hotkeys']),
  ('Игровые возможности','game',['disable_game_bar','disable_fullscreen_optimization']),
  ('Поведение системы','settings',['auto_kill_hung_apps','disable_recent_history'])],
 'Внешний вид':[
  ('Ярлыки','link',['remove_shortcut_text','remove_shortcut_arrow']),
  ('Корзина','trash',['recycle_bin_theme','recycle_bin_explorer'])],
 'Конфиденциальность':[
  ('Приватность','shield',['disable_global_telemetry','disable_uwp_background','disable_maps_auto_update']),
  ('Безопасность и доступ','settings',['disable_file_security_warnings','admin_group','disable_uac','disable_spectre_meltdown'])],
 'Приложения':[('Обновления приложений','apps',['disable_store_app_auto_update'])]}

def label(text,size=15,color=TEXT,wrap=False):
    w=QLabel(text);w.setFont(font(size));w.setStyleSheet(f'color:{color};background:transparent;font-size:{size}px;')
    w.setWordWrap(wrap);w.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred);return w

class WindowButton(QAbstractButton):
    def __init__(self,kind,command):
        super().__init__();self.kind=kind;self.setFixedSize(50,36);self.setCursor(Qt.PointingHandCursor);self.clicked.connect(command)
        self.setAccessibleName({'min':'Свернуть','max':'Развернуть или восстановить','close':'Закрыть'}[kind])
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.setPen(Qt.NoPen);p.setBrush(QColor('#b63845') if self.kind=='close' else QColor(141,165,204,30));p.drawRoundedRect(QRectF(self.rect()).adjusted(3,2,-3,-2),6,6)
        p.setPen(QPen(QColor(TEXT),1))
        if self.kind=='min':p.drawLine(19,18,30,18)
        elif self.kind=='max':p.drawRoundedRect(QRectF(20,13,10,10),1,1)
        else:p.drawLine(20,13,30,23);p.drawLine(30,13,20,23)
    def enterEvent(self,e):self.update()
    def leaveEvent(self,e):self.update()

class TitleBar(QWidget):
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:self.window().windowHandle().startSystemMove()
    def mouseDoubleClickEvent(self,e):
        if e.button()==Qt.LeftButton:self.window().maximize_restore()

class FeatureRow(QWidget):
    def __init__(self,app,fid,icon='sliders'):
        super().__init__();self.fid=fid;self.app=app
        layout=QHBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        layout.addWidget(Icon(icon,22));layout.addSpacing(12)
        self.dot=label('●',8,MUTED);self.dot.setFixedWidth(10);layout.addWidget(self.dot);layout.addSpacing(4)
        self.title=label(app.features[fid]['title'],15,wrap=True);self.title.setCursor(Qt.PointingHandCursor)
        self.title.mouseReleaseEvent=lambda e:app.details(fid);self.title.setToolTip('Показать все проверяемые параметры')
        layout.addWidget(self.title,1);layout.addSpacing(12)
        self.switch=Switch(lambda checked:app.toggle(fid));layout.addWidget(self.switch)
        self.switch.setAccessibleName(app.features[fid]['title']);self.setMinimumHeight(36)
    def set_state(self,result,available):
        status=result.get('status','unknown');color={'enabled':GREEN,'partial':YELLOW,'disabled':'#697990','unknown':YELLOW}[status]
        owned=self.fid in self.app.controller.state['features']
        self.dot.setStyleSheet(f'color:{color};background:transparent;');self.switch.setChecked(owned);self.switch.setEnabled(available)
        self.switch.setToolTip({'enabled':'Проверенные параметры совпадают (не означает измеренный прирост производительности)',
                                'partial':'Есть расхождения, ожидание перезагрузки или ошибки; нажмите название',
                                'disabled':'Параметры не совпадают',
                                'unknown':'Недостаточно данных для проверки'}[status])

class Panel(GlassCard):
    def __init__(self,title,icon='settings'):
        super().__init__();self.content=QVBoxLayout(self);self.content.setContentsMargins(22,17,22,18);self.content.setSpacing(0)
        header=QHBoxLayout();header.setSpacing(20);header.addWidget(Icon(icon,29));header.addWidget(label(title,20),1)
        self.content.addLayout(header);self.content.addSpacing(15);self.content.addStretch(1)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
    def add(self,widget,spacing=0):
        self.content.insertWidget(self.content.count()-1,widget)
        if spacing:self.content.insertSpacing(self.content.count()-1,spacing)

class App(QWidget):
    def __init__(self,preview=False):
        super().__init__();self.preview=preview;self.setWindowTitle('BBYS — Build By yourself')
        self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint|Qt.WindowMinMaxButtonsHint)
        # On Windows DWM supplies the alpha surface. A layered Qt window makes
        # the acrylic rectangular even when its painter/region is rounded.
        if sys.platform!='win32':self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName('BBYSWindow');self.setAutoFillBackground(False)
        self.setMouseTracking(True);self.setMinimumSize(1080,720);self.resize(1362,998);self.setStyleSheet(STYLE+'\n#BBYSWindow {background:transparent;}')
        self.setWindowIcon(QIcon(str(ASSETS/'BBYS_icon_pack'/'BBYS.ico')))
        self.queue=queue.Queue();self.busy=False;self.checking=False;self.rows={};self.results={};self.panels=[]
        self.features=json.loads((ASSETS/'bbys_features.json').read_text(encoding='utf-8'))
        self.features['mahashe_settings']['title']='Параметры навигации BBYS';self.features['take_ownership_menu']['title']='«Стать владельцем» в контекстном меню'
        self.backend=WindowsBackend(APP_DIR);self.controller=Controller(self.backend,self.features,APP_DIR/'source'/'appsource'/'state'/'bbys-settings.json')
        self.native_glass={'mode':'pending','native':False};self._glass_applied=False
        self.glass_timer=QTimer(self);self.glass_timer.setSingleShot(True);self.glass_timer.timeout.connect(self.apply_glass)
        self.make_layout();self.show_page('Проводник')
        self.timer=QTimer(self);self.timer.timeout.connect(self.drain);self.timer.start(100)
        self.refresh_shortcut=QShortcut(QKeySequence('F5'),self);self.refresh_shortcut.activated.connect(self.refresh)
        if not preview:QTimer.singleShot(500,self.refresh)
    def make_layout(self):
        self.sidebar=QWidget(self);self.sidebar.setFixedWidth(SIDEBAR_WIDTH)
        side=QVBoxLayout(self.sidebar);side.setContentsMargins(12,20,10,19);side.setSpacing(6)
        self.brand=TitleBar(self.sidebar);self.brand.setFixedHeight(75)
        logo=QLabel(self.brand);logo.setGeometry(9,0,54,54)
        logo.setPixmap(QIcon(str(ASSETS/'BBYS_icon_pack'/'BBYS.ico')).pixmap(54,54));logo.setAttribute(Qt.WA_TransparentForMouseEvents)
        brand_label=label('BBYS (Build By yourself)',18);brand_label.setParent(self.brand);brand_label.setGeometry(74,8,196,38);brand_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        side.addWidget(self.brand);self.nav={}
        for name,icon in NAV:
            button=NavButton(name,icon,lambda checked=False,n=name:self.show_page(n));side.addWidget(button);self.nav[name]=button
        side.addStretch(1)
        separator=QWidget();separator.setFixedHeight(1);separator.setStyleSheet('background:rgba(125,154,194,65);')
        line=QHBoxLayout();line.setContentsMargins(18,0,16,0);line.addWidget(separator);side.addLayout(line);side.addSpacing(5)
        for name,icon in [('Настройки','settings'),('О программе','info')]:
            button=NavButton(name,icon,lambda checked=False,n=name:self.show_page(n));side.addWidget(button);self.nav[name]=button
        self.titlebar=TitleBar(self);self.status_label=label('',13,MUTED);self.status_label.setParent(self.titlebar);self.status_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        controls=QHBoxLayout(self.titlebar);controls.setContentsMargins(0,6,8,10);controls.setSpacing(2);controls.addStretch()
        for kind,command in [('min',self.showMinimized),('max',self.maximize_restore),('close',self.close)]:controls.addWidget(WindowButton(kind,command))
        self.scroll=QScrollArea(self);self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setAutoFillBackground(False);self.scroll.viewport().setAutoFillBackground(False)
        self.body=QWidget();self.scroll.setWidget(self.body)
        # QScrollArea.setWidget enables autoFillBackground on its content.
        # Disable it afterwards, otherwise it hides the acrylic below cards.
        self.body.setAutoFillBackground(False);self.scroll.viewport().setAutoFillBackground(False)
        self.grid=QGridLayout(self.body);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(14);self.grid.setAlignment(Qt.AlignTop);self.columns=2
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        # Replace the backing-store pixels, rather than blend translucent ink
        # over the palette's opaque window brush on a regular HWND.
        p.setCompositionMode(QPainter.CompositionMode_Source);p.fillRect(self.rect(),Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        radius=0 if self.isMaximized() else WINDOW_RADIUS;path=QPainterPath();path.addRoundedRect(r,radius,radius);p.setClipPath(path)
        p.fillPath(path,QColor(8,18,29,115))
        gradient=QLinearGradient(0,0,SIDEBAR_WIDTH,self.height());gradient.setColorAt(0,QColor(45,66,99,43));gradient.setColorAt(.55,QColor(18,36,60,18));gradient.setColorAt(1,QColor(43,65,91,39))
        p.fillRect(QRectF(0,0,SIDEBAR_WIDTH,self.height()),gradient);p.setPen(QPen(QColor(128,158,199,49),1));p.drawLine(SIDEBAR_WIDTH,0,SIDEBAR_WIDTH,self.height())
        p.setClipping(False);p.setPen(QPen(QColor(126,163,211,120),1));p.setBrush(Qt.NoBrush);p.drawPath(path)
    def showEvent(self,e):
        super().showEvent(e)
        self.glass_timer.start(0)
    def apply_glass(self):
        # Qt updates the native frame during show/resize. Configure DWM after
        # those events have completed, otherwise Qt resets its alpha surface.
        self.native_glass=enable_native_glass(int(self.winId()));self._glass_applied=True
        if self.isMaximized():self.clearMask()
        else:
            path=QPainterPath();path.addRoundedRect(QRectF(self.rect()),WINDOW_RADIUS,WINDOW_RADIUS)
            self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        clip_native_window(int(self.winId()),0 if self.isMaximized() else WINDOW_RADIUS*self.devicePixelRatioF())
        self.update()
    def resizeEvent(self,e):
        if hasattr(self,'sidebar'):
            self.sidebar.setGeometry(0,0,SIDEBAR_WIDTH,self.height());self.titlebar.setGeometry(SIDEBAR_WIDTH,0,self.width()-SIDEBAR_WIDTH,58)
            self.status_label.setGeometry(22,15,max(1,self.titlebar.width()-195),26)
            self.scroll.setGeometry(SIDEBAR_WIDTH+20,58,self.width()-SIDEBAR_WIDTH-40,self.height()-74);self.reflow()
            self.glass_timer.start(0)
        super().resizeEvent(e)
    def mousePressEvent(self,e):
        if e.button()!=Qt.LeftButton:return
        x,y=e.position().x(),e.position().y();edge=Qt.Edges()
        if not self.isMaximized():
            if x<7:edge|=Qt.LeftEdge
            if x>self.width()-7:edge|=Qt.RightEdge
            if y<7:edge|=Qt.TopEdge
            if y>self.height()-7:edge|=Qt.BottomEdge
        if edge:self.windowHandle().startSystemResize(edge)
        elif y<58:self.windowHandle().startSystemMove()
    def maximize_restore(self):
        if self.isMaximized():self.showNormal()
        else:self.showMaximized()
        self.update()
    def set_status(self,text):
        self.status_label.setText(self.status_label.fontMetrics().elidedText(str(text),Qt.ElideRight,self.status_label.width()));self.status_label.setToolTip(str(text))
    def panel(self,title,icon='settings'):
        p=Panel(title,icon);self.panels.append(p);return p
    def reflow(self):
        columns=2 if self.scroll.viewport().width()>=735 else 1;self.columns=columns
        for i,p in enumerate(self.panels):self.grid.addWidget(p,i//columns,i%columns)
        self.grid.setColumnStretch(0,1);self.grid.setColumnStretch(1,1 if columns==2 else 0)
    def feature_row(self,parent,fid,icon='sliders'):
        row=FeatureRow(self,fid,icon);parent.add(row,2);self.rows[fid]=row;return row
    def note(self,parent,text):
        w=label(text,14,MUTED,True);parent.add(w,12);return w
    def action(self,parent,title,command,caption='Выполнить',icon=None,confirm=True):
        row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.setSpacing(12)
        if icon:layout.addWidget(Icon(icon,22))
        layout.addWidget(label(title,15,wrap=True),1)
        button=GlassButton(caption,lambda:self.run_action(title,command) if confirm else command(),width=120);layout.addWidget(button);parent.add(row,2);return button
    def link(self,parent,title,page,icon='folder',caption='Открыть'):
        return self.action(parent,title,lambda:self.show_page(page),caption,icon,confirm=False)
    def show_page(self,name):
        if self.busy:return
        self.active=name;selected='Дополнительно' if name in EXTRA else name
        for title,button in self.nav.items():button.selected=title==selected;button.update()
        while self.grid.count():
            item=self.grid.takeAt(0)
            if item.widget():item.widget().hide();item.widget().deleteLater()
        self.rows={};self.panels=[];self.scroll.verticalScrollBar().setValue(0)
        for title,icon,fids in SECTIONS.get(name,[]):
            p=self.panel(title,icon)
            for fid in fids:self.feature_row(p,fid,icon)
        if name=='Проводник':self.explorer_page()
        elif name=='Система':
            p=self.panel('Системные действия','terminal')
            for title,method in [('Защитник Windows','run_defender_tool'),('Windows 11 AI','run_remove_windows_ai_script'),('Win11 Debloat','run_win11_debloat')]:self.action(p,title,lambda m=method:self.legacy(m),icon='terminal')
            self.action(p,'Восстановить Utilman.exe',self.utilman,icon='keyboard')
        elif name=='Приложения':
            p=self.panel('Удаление компонентов','trash');self.action(p,'GIGABYTE Dynamic Lighting module',uninstall_lighting,'Удалить')
            self.action(p,'Microsoft Edge',lambda:self.legacy('enable_edge_disable'),'Удалить');self.action(p,'Предустановленные приложения Windows',lambda:self.legacy('run_remove_preinstalled_apps'),'Удалить')
        elif name=='Автозагрузка':
            p=self.panel('Приложения при входе','play');self.action(p,'Автозагрузка Windows',lambda:self.open_settings('ms-settings:startupapps'),'Открыть',confirm=False)
            self.action(p,'Папка автозагрузки пользователя',lambda:self.open_folder(os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')),'Открыть',confirm=False)
            self.note(p,'Список приложений и их переключатели доступны в параметрах Windows.')
        elif name=='Сеть':
            p=self.panel('Сеть и подключения','globe');self.action(p,'Параметры сети',lambda:self.open_settings('ms-settings:network-status'),'Открыть',confirm=False)
            self.action(p,'Сброс кеша и сети',lambda:self.legacy('reset_cache_and_network'),'Сбросить')
        elif name=='Дополнительно':
            for title,icon,text in [('Папки','folder','Расположение системных папок'),('TEMP','trash','Временные файлы пользователя и системы'),('PATH','terminal','Каталоги поиска консольных команд'),('Утилиты','apps','Установленные инструменты')]:
                p=self.panel(title,icon);self.link(p,text,title,icon)
        elif name=='TEMP':self.temp_page()
        elif name=='Папки':self.folders_page()
        elif name=='PATH':self.path_page()
        elif name=='Утилиты':self.utilities_page()
        elif name=='Настройки':
            p=self.panel('Внешний вид','palette');self.note(p,'Полупрозрачное окно с размытием фона Windows. Текст и элементы управления сохраняют полную непрозрачность.')
            p=self.panel('Проверка состояния','list');self.note(p,'● Зелёный — все параметры совпали.\n● Жёлтый — параметры отличаются или недоступны для проверки.\n● Серый — настройка не применена.\n\nНажмите название функции для подробностей. F5 обновляет состояние.')
            self.action(p,'Проверить параметры Windows',self.refresh,'Обновить',confirm=False)
        elif name=='О программе':
            p=self.panel('BBYS','info');self.note(p,'Build By yourself\nВерсия 6.4.1\n\nНастройка Windows, Проводника, папок и окружения.\nОсновано на WinTweaker 6_4.')
        self.reflow();self.render_states()
    def explorer_page(self):
        p=self.panel('Внешний вид','palette')
        for fid in ('remove_shortcut_text','remove_shortcut_arrow','recycle_bin_theme'):self.feature_row(p,fid,'palette')
        p=self.panel('Навигация и файлы','file');self.feature_row(p,'recycle_bin_explorer','folder');self.feature_row(p,'mahashe_settings','list')
        p=self.panel('Контекстное меню','folder');self.feature_row(p,'take_ownership_menu','folder');self.feature_row(p,'context_menu_extension','folder')
        self.action(p,'Параметры папок Windows',self.folder_options,'Открыть',icon='file',confirm=False)
        p=self.panel('Контекстное меню','list');self.feature_row(p,'take_ownership_menu','shield');self.feature_row(p,'context_menu_extension','list')
        p=self.panel('Быстрый доступ','star');self.feature_row(p,'disable_recent_history','clock')
        self.action(p,'Открыть Проводник',lambda:self.open_folder(str(Path.home())),'Открыть',icon='folder',confirm=False)
        p=self.panel('Системные папки','folder')
        for title,key,icon in FOLDERS:self.link(p,title,'Папки',icon,'Изменить')
        p=self.panel('Дополнительно','settings');self.link(p,'Расположение TEMP и TMP','TEMP','trash','Изменить')
        self.link(p,'Переменная окружения PATH','PATH','terminal','Изменить');self.link(p,'Встроенные утилиты','Утилиты','apps')
        for panel in self.panels:panel.setMinimumHeight(296)
    def open_settings(self,uri):
        if not self.preview:os.startfile(uri)
    def open_folder(self,path):
        if not self.preview:os.startfile(path)
    def folder_options(self):
        if self.preview:return
        import subprocess
        subprocess.Popen(['control.exe','folders'],creationflags=subprocess.CREATE_NO_WINDOW)
    def path_input(self,parent,title,value):
        parent.add(label(title,14,MUTED),6);row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
        entry=QLineEdit(value);entry.setMinimumWidth(100);entry.setAccessibleName(title);layout.addWidget(entry,1)
        layout.addWidget(GlassButton('…',lambda:self.choose(entry),width=36));parent.add(row,12);return entry
    def choose(self,entry):
        if self.preview:return
        path=entry.text();value=QFileDialog.getExistingDirectory(self,'Выберите папку',path if Path(path).is_dir() else str(APP_DIR))
        if value:entry.setText(os.path.normpath(value))
    def temp_page(self):
        self.temp_vars={};state=bbys_temp.current() if not self.preview else {f'{s}_{n}':{'data':f'D:\\Temp\\{s}'} for s in ('user','machine') for n in ('temp','tmp')}
        for scope,title in [('user','TEMP пользователя'),('machine','TEMP системы')]:
            p=self.panel(title,'trash')
            for name in ('temp','tmp'):
                k=f'{scope}_{name}';self.temp_vars[k]=self.path_input(p,name.upper(),os.path.expandvars(state[k].get('data','')))
        p=self.panel('Переключение TEMP/TMP','settings');self.note(p,'Проверяются путь, права доступа и запись файлов. Существующие временные файлы остаются на прежнем месте.')
        self.action(p,'Сохранить расположения',self.save_temp,'Применить',confirm=False)
    def save_temp(self):
        values={k:v.text() for k,v in self.temp_vars.items()};self.run_action('Переключить TEMP/TMP',lambda:bbys_temp.switch(values))
    def folders_page(self):
        self.folder_vars={};key=r'HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
        for title,name,icon in FOLDERS:
            p=self.panel(title,icon);state=reg.read(key,name) if not self.preview else {'data':'D:\\'+title}
            self.folder_vars[name]=self.path_input(p,'Расположение',os.path.expandvars(state.get('data','')))
        p=self.panel('Сохранение расположений','settings');self.note(p,'Изменяется расположение системных папок. Файлы автоматически не переносятся.')
        self.action(p,'Сохранить расположения',self.save_folders,'Применить',confirm=False)
    def save_folders(self):
        values={k:v.text() for k,v in self.folder_vars.items()}
        def work():
            import bbys_folders
            return bbys_folders.switch(values)
        self.run_action('Изменить расположение папок',work)
    def path_page(self):
        self.path_editors={}
        for scope,title in [('user','PATH пользователя'),('machine','PATH системы')]:
            p=self.panel(title,'terminal');value=reg.read(bbys_temp.SCOPES[scope],'Path').get('data','') if not self.preview else r'C:\Windows\System32;D:\Tools'
            self.note(p,'Один каталог в строке. Порядок поиска сохраняется.');edit=QPlainTextEdit();edit.setPlainText('\n'.join(value.split(';')));edit.setMinimumHeight(280)
            p.add(edit);self.path_editors[scope]=(edit,value)
        p=self.panel('Консольные команды','terminal');self.feature_row(p,'cmd_command_extension','terminal')
        self.action(p,'Сохранить PATH',self.save_path,'Применить',confirm=False);self.action(p,'Восстановить стандартный PATH',lambda:self.legacy('restore_standard_path'),'Восстановить')
    def save_path(self):
        values={s:(';'.join(p.strip() for p in edit.toPlainText().splitlines() if p.strip()),old) for s,(edit,old) in self.path_editors.items()}
        def work():
            old={s:reg.read(bbys_temp.SCOPES[s],'Path') for s in values};touched=[]
            try:
                for scope,(v,original) in values.items():
                    if old[scope].get('data','')!=original:raise RuntimeError('PATH изменён извне. Откройте страницу заново.')
                    if v==original:continue
                    for prop in self.controller.state['properties'].values():
                        op=prop['op']
                        if op['kind']=='path_item' and op.get('key')==bbys_temp.SCOPES[scope] and prop['owners']:
                            target=self.backend.expand(op['name'])
                            if target.casefold() not in [x.casefold() for x in v.split(';')]:raise RuntimeError('Каталог используется активной функцией: '+target)
                    touched.append(scope);reg.write(bbys_temp.SCOPES[scope],'Path',{'exists':True,'type':2,'data':v})
                    if reg.read(bbys_temp.SCOPES[scope],'Path')['data']!=v:raise RuntimeError('Проверка PATH не пройдена.')
            except Exception:
                for scope in reversed(touched):reg.write(bbys_temp.SCOPES[scope],'Path',old[scope])
                raise
            broadcast_environment();return 'PATH сохранён и проверен.'
        self.run_action('Сохранить PATH',work)
    def utilities_page(self):
        p=self.panel('Установленные утилиты','apps');found=False;base=APP_DIR/'source'/'Utility'
        if base.is_dir():
            for folder in sorted(base.iterdir()):
                files=list(folder.glob('*.exe')) if folder.is_dir() else ([folder] if folder.suffix.lower()=='.exe' else [])
                if files:found=True;self.action(p,folder.stem,lambda path=files[0]:os.startfile(path),'Открыть')
        if not found:self.note(p,'Поместите утилиту в отдельную папку source/Utility.')
    def legacy(self,method):
        import bbys_engine
        engine=bbys_engine.WindowsTweaksEngine(lambda t:self.queue.put(('log',t)));engine.snapshot=lambda *a,**k:None;getattr(engine,method)()
        return 'Действие выполнено. Внешние утилиты проверяют результат в собственном окне.'
    def utilman(self):
        import bbys_engine
        engine=bbys_engine.WindowsTweaksEngine(lambda t:self.queue.put(('log',t)))
        if engine.check_utilman_cmd():
            engine.disable_utilman_cmd()
            if engine.check_utilman_cmd():raise RuntimeError('Не удалось восстановить исходный Utilman.exe. Проверьте наличие оригинала.')
            return 'Восстановлен исходный Utilman.exe.'
        raise RuntimeError('Подмена Utilman.exe не поддерживается. Для восстановления оригинального файла используйте штатные средства Windows.')
    def toggle(self,fid):
        enabled=fid not in self.controller.state['features'];self.render_states()
        self.run_action(('Применить: ' if enabled else 'Отключить: ')+self.features[fid]['title'],lambda:self.controller.set_feature(fid,enabled))
    def run_action(self,title,command):
        if self.preview:return
        if self.busy or self.checking:QMessageBox.information(self,'BBYS','Дождитесь завершения текущей операции.');return
        detail='\n\nДля замены Utilman будет сохранён оригинальный файл для возврата.' if 'Спецвозможности' in title else ''
        if QMessageBox.question(self,'BBYS',title+'?'+detail,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        self.busy=True;self.set_status(title+'…');self.render_states()
        def work():
            try:self.queue.put(('done',command()))
            except Exception as exc:self.queue.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()
    def refresh(self):
        if self.preview or self.busy or self.checking:return
        self.checking=True;self.set_status('Проверка параметров Windows…');self.render_states()
        def work():
            try:
                self.backend.refresh();result={fid:self.controller.check(fid) for fid in self.features if fid not in ('disable_edge','utilman_cmd')};self.queue.put(('states',result))
            except Exception as exc:self.queue.put(('check_error',str(exc)))
        threading.Thread(target=work,daemon=True).start()
    def render_states(self):
        for fid,row in self.rows.items():row.set_state(self.results.get(fid,{}),not(self.busy or self.checking))
    def details(self,fid):
        data=self.results.get(fid)
        if not data:
            if not self.preview:QMessageBox.information(self,'BBYS','Состояние ещё не проверено.')
            return
        dialog=QDialog(self);dialog.setWindowTitle(self.features[fid]['title']);dialog.resize(820,540)
        layout=QVBoxLayout(dialog);layout.setContentsMargins(18,18,18,18);layout.setSpacing(14);text=QPlainTextEdit();text.setReadOnly(True);layout.addWidget(text)
        names={'match':'Совпадает','mismatch':'Отличается','unknown':'Не проверено','na':'Отсутствует в системе'};lines=[]
        if data.get('notice'):lines.append(data['notice'])
        for c in data['checks']:
            lines.append(names[c['status']]+' — '+c['name'])
            if c['status'] in ('mismatch','unknown'):lines.append('  '+str(c.get('error',f"Ожидалось: {c.get('expected')}; фактически: {c.get('actual')}")))
        text.setPlainText('\n'.join(lines));buttons=QHBoxLayout();buttons.addStretch();layout.addLayout(buttons)
        def change(enabled):
            dialog.accept();self.run_action(('Применить: ' if enabled else 'Отменить изменения BBYS: ')+self.features[fid]['title'],lambda:self.controller.set_feature(fid,enabled))
        if fid in self.controller.state['features']:buttons.addWidget(GlassButton('Отменить',lambda:change(False)))
        buttons.addWidget(GlassButton('Применить',lambda:change(True),primary=True));dialog.exec()
    def drain(self):
        try:
            while True:
                kind,payload=self.queue.get_nowait()
                if kind=='states':self.results=payload;self.checking=False;self.render_states();self.set_status('')
                elif kind=='check_error':
                    self.checking=False;self.set_status('Проверка недоступна: '+payload)
                    self.results={fid:{'status':'partial','checks':[{'name':'Проверка системы','status':'unknown','error':payload}]} for fid in self.features};self.render_states()
                elif kind=='log':self.set_status(payload)
                elif kind in ('done','error'):
                    self.busy=False
                    if kind=='error':QMessageBox.critical(self,'BBYS',payload)
                    elif isinstance(payload,dict):
                        if payload.get('errors'):QMessageBox.warning(self,'BBYS','Применено частично:\n'+'\n'.join(payload['errors'][:12]))
                        elif payload.get('shared'):QMessageBox.information(self,'BBYS','Настройка остаётся активной: её параметры нужны другой включённой функции.')
                        elif payload.get('status')!='enabled' and not payload.get('notice'):
                            QMessageBox.warning(self,'BBYS','Операция завершена, но итоговая проверка не подтвердила полное применение. Нажмите название функции для подробностей.')
                        if payload.get('notice'):QMessageBox.information(self,'BBYS — ограничения',payload['notice'])
                    else:QMessageBox.information(self,'BBYS',str(payload or 'Готово'))
                    self.refresh()
        except queue.Empty:pass
    def closeEvent(self,e):
        if self.busy:QMessageBox.information(self,'BBYS','Дождитесь завершения изменения параметров.');e.ignore()
        else:e.accept()

def main():
    try:ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('BBYS.BuildByYourself.6.4.1')
    except (AttributeError,OSError):pass
    app=QApplication(sys.argv);app.setApplicationName('BBYS');app.setOrganizationName('BBYS');app.setFont(font())
    window=App(preview='--preview' in sys.argv)
    smoke=window.preview and '--smoke-test' in sys.argv
    screen=(app.screens()[1] if smoke and len(app.screens())>1 else app.primaryScreen()).availableGeometry()
    if smoke:window.setAttribute(Qt.WA_ShowWithoutActivating)
    if window.height()>screen.height()-40:window.resize(min(1362,screen.width()-40),screen.height()-40)
    window.move(screen.center()-window.rect().center());window.show()
    if smoke:QTimer.singleShot(1800,app.quit)
    sys.exit(app.exec())
