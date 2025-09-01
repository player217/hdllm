# src/ui_user_tab.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QLineEdit, QListWidget, QListWidgetItem, QFileDialog, QGroupBox, QSpacerItem,
    QSizePolicy, QAbstractItemView, QRadioButton, QButtonGroup
)

class UserTab(QWidget):
    # 메인 로직과 연결할 시그널들
    qdrantPathChanged = Signal(str)
    qdrantScopeChanged = Signal(str)                # 'personal' or 'dept'
    outlookLiveToggled = Signal(bool)
    mailsSelected = Signal(list)                    # [message_id or subject...]
    embedFromPathRequested = Signal(str)            # dir path
    embedResumeRequested = Signal()
    embedFreshRequested = Signal()
    embedRestoreRequested = Signal()
    runWholeAppRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qdrant_path = ""
        self._mail_items = []  # [(id, subject, sender, checked)]
        self._build_ui()

    # ------------ UI 구성 ------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # 1) Qdrant DB 설정
        box_db = QGroupBox("Qdrant DB 설정")
        db_layout = QVBoxLayout()
        
        # 1-1) 스코프 선택 (Personal vs Department)
        scope_layout = QHBoxLayout()
        scope_layout.addWidget(QLabel("검색 범위:"))
        
        self.radio_personal = QRadioButton("개인 PC (127.0.0.1)")
        self.radio_dept = QRadioButton("부서 서버 (10.150.104.37)")
        self.radio_personal.setChecked(True)  # 기본값: 개인 PC
        
        self.scope_group = QButtonGroup()
        self.scope_group.addButton(self.radio_personal, 0)
        self.scope_group.addButton(self.radio_dept, 1)
        self.scope_group.buttonClicked.connect(self._on_scope_changed)
        
        scope_layout.addWidget(self.radio_personal)
        scope_layout.addWidget(self.radio_dept)
        scope_layout.addStretch()
        db_layout.addLayout(scope_layout)
        
        # 1-2) 로컬 DB 경로 (개인 PC용)
        path_layout = QHBoxLayout()
        self.ed_qdrant = QLineEdit()
        self.ed_qdrant.setPlaceholderText("예) C:\\data\\qdrant")
        btn_browse = QPushButton("찾아보기…")
        btn_browse.clicked.connect(self._pick_qdrant_dir)
        path_layout.addWidget(QLabel("로컬 경로:"))
        path_layout.addWidget(self.ed_qdrant)
        path_layout.addWidget(btn_browse)
        db_layout.addLayout(path_layout)
        
        box_db.setLayout(db_layout)
        root.addWidget(box_db)

        # 2) Outlook / 메일
        row = QHBoxLayout()

        # 2-1) Outlook 라이브
        box_outlook = QGroupBox("라이브 Outlook")
        ol_l = QVBoxLayout()
        self.chk_outlook = QCheckBox("Outlook 실시간 사용")
        self.chk_outlook.stateChanged.connect(
            lambda s: self.outlookLiveToggled.emit(s == Qt.Checked)
        )
        self.lbl_account = QLabel("계정: (미연결)")
        self.lbl_account.setStyleSheet("color: #666;")
        ol_l.addWidget(self.chk_outlook)
        ol_l.addWidget(self.lbl_account)
        box_outlook.setLayout(ol_l)
        row.addWidget(box_outlook, 1)

        # 2-2) 메일 선택
        box_mail = QGroupBox("메일 선택")
        mail_l = QVBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("제목/발신자 검색")
        self.list_mails = QListWidget()
        self.list_mails.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_mails.setAlternatingRowColors(True)
        self.list_mails.setMinimumHeight(180)
        search.textChanged.connect(self._filter_mail_list)
        mail_l.addWidget(search)
        mail_l.addWidget(self.list_mails)
        box_mail.setLayout(mail_l)
        row.addWidget(box_mail, 2)

        root.addLayout(row)

        # 3) 임베딩 액션 버튼 4개 (경로, 이어서, 새롭게, 기록복구)
        box_embed = QGroupBox("임베딩")
        em_l = QHBoxLayout()
        self.btn_path = QPushButton("경로로 임베딩")
        self.btn_resume = QPushButton("이어하기")
        self.btn_fresh = QPushButton("새로 시작")
        self.btn_restore = QPushButton("기록 복구")
        self.btn_path.clicked.connect(self._pick_embed_path)
        self.btn_resume.clicked.connect(self.embedResumeRequested.emit)
        self.btn_fresh.clicked.connect(self.embedFreshRequested.emit)
        self.btn_restore.clicked.connect(self.embedRestoreRequested.emit)
        for b in (self.btn_path, self.btn_resume, self.btn_fresh, self.btn_restore):
            b.setMinimumHeight(36)
        em_l.addWidget(self.btn_path)
        em_l.addWidget(self.btn_resume)
        em_l.addWidget(self.btn_fresh)
        em_l.addWidget(self.btn_restore)
        box_embed.setLayout(em_l)
        root.addWidget(box_embed)

        # 4) 하단: 전체 앱 실행 + 상태 배지
        bottom = QHBoxLayout()
        self.btn_run_all = QPushButton("전체 앱 실행")
        self.btn_run_all.setMinimumHeight(40)
        self.btn_run_all.clicked.connect(self.runWholeAppRequested.emit)
        bottom.addWidget(self.btn_run_all)

        bottom.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.badge_qdrant = _Badge("Qdrant: unknown", "unknown")
        self.badge_outlook = _Badge("Outlook: off", "fail")
        self.badge_backend = _Badge("Backend: unknown", "unknown")
        for b in (self.badge_backend, self.badge_qdrant, self.badge_outlook):
            bottom.addWidget(b)
        root.addLayout(bottom)

        # 스타일(가벼운 뱃지)
        self.setStyleSheet("""
        QGroupBox { font-weight:600; }
        QPushButton { font-weight:600; }
        """)

        # 초기 이벤트
        self.ed_qdrant.textChanged.connect(self._on_qdrant_path_changed)

    # ------------ 공개 메서드 (메인에서 데이터 바인딩) ------------
    def setQdrantPath(self, path: str):
        self._qdrant_path = path or ""
        self.ed_qdrant.setText(self._qdrant_path)

    def setOutlookAccount(self, account_email: str | None):
        self.lbl_account.setText(f"계정: {account_email or '(미연결)'}")

    def setMailList(self, items: list[tuple]):
        """items: [(id, subject, sender), ...]"""
        self._mail_items = [(i[0], i[1], i[2], False) for i in items]
        self._rebuild_mail_list()

    def setStatus(self, *, backend: str, qdrant: str, outlook: str):
        """각 값: 'ok'|'warn'|'fail'|'unknown'"""
        self.badge_backend.updateState(f"Backend: {backend}", backend)
        self.badge_qdrant.updateState(f"Qdrant: {qdrant}", qdrant)
        self.badge_outlook.updateState(f"Outlook: {outlook}", outlook)

    def selectedMailIds(self) -> list[str]:
        out = []
        for row in range(self.list_mails.count()):
            item = self.list_mails.item(row)
            if item.checkState() == Qt.Checked:
                out.append(item.data(Qt.UserRole))
        return out

    # ------------ 내부 핸들러 ------------
    def _pick_qdrant_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Qdrant DB 폴더 선택")
        if d:
            self.setQdrantPath(d)

    def _on_qdrant_path_changed(self, text: str):
        self._qdrant_path = text.strip()
        self.qdrantPathChanged.emit(self._qdrant_path)
    
    def _on_scope_changed(self):
        """Qdrant 스코프 변경 핸들러"""
        if self.radio_personal.isChecked():
            scope = "personal"
        else:
            scope = "dept"
        
        # 로컬 경로 입력 필드 활성화/비활성화
        self.ed_qdrant.setEnabled(scope == "personal")
        
        # 시그널 발생
        self.qdrantScopeChanged.emit(scope)
        
        print(f"Qdrant 스코프 변경됨: {scope}")  # 디버그용

    def _pick_embed_path(self):
        d = QFileDialog.getExistingDirectory(self, "임베딩할 폴더 선택")
        if d:
            self.embedFromPathRequested.emit(d)

    def _rebuild_mail_list(self, filter_text: str = ""):
        self.list_mails.clear()
        f = filter_text.lower().strip()
        for mid, subj, sender, _ in self._mail_items:
            label = f"{subj}  —  {sender}"
            if f and f not in label.lower():
                continue
            it = QListWidgetItem(label)
            it.setCheckState(Qt.Unchecked)
            it.setData(Qt.UserRole, mid)
            self.list_mails.addItem(it)

    def _filter_mail_list(self, text: str):
        self._rebuild_mail_list(text)


class _Badge(QLabel):
    _colors = {
        "ok":       "background:#16a34a;color:#fff;",
        "warn":     "background:#f59e0b;color:#fff;",
        "fail":     "background:#dc2626;color:#fff;",
        "unknown":  "background:#e5e7eb;color:#374151;",
    }
    def __init__(self, text: str, state: str = "unknown"):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(110)
        self.setStyleSheet("padding:5px 10px;border-radius:10px;" + self._colors.get(state, ""))

    def updateState(self, text: str, state: str):
        self.setText(text)
        self.setStyleSheet("padding:5px 10px;border-radius:10px;" + self._colors.get(state, ""))