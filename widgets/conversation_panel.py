"""
Redesigned Conversation Panel - Clean modern chat sidebar.

Features:
- Proper padding and spacing
- Styled user/assistant message cards
- Styled scrollbar
- Auto-scroll to newest message
- No text clipping
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QFrame, QPushButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class ConversationPanel(QWidget):
    """Modern conversation panel with proper message cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self.setStyleSheet("""
            ConversationPanel {
                background: #141416;
                border-left: 1px solid #252528;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet("""
            QWidget {
                background: #141416;
                border-bottom: 1px solid #252528;
            }
        """)
        hdr_lay = QHBoxLayout(header)
        hdr_lay.setContentsMargins(20, 0, 20, 0)

        title = QLabel("Conversation")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        title.setStyleSheet("color: #F5F5F7; background: transparent; border: none;")
        hdr_lay.addWidget(title)

        hdr_lay.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(52, 28)
        clear_btn.setFont(QFont("Segoe UI", 10))
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #1c1c20;
                color: #71717A;
                border: 1px solid #252528;
                border-radius: 6px;
            }
            QPushButton:hover {
                color: #A1A1AA;
                border-color: #3a3a42;
            }
        """)
        clear_btn.clicked.connect(self.clear_messages)
        hdr_lay.addWidget(clear_btn)

        root.addWidget(header)

        # ── Scroll area ───────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #141416;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #303035;
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3a3a42;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 16, 0, 16)
        self._container_layout.setSpacing(4)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, stretch=1)

        self._msg_count = 0

    def add_message(self, sender: str, text: str) -> None:
        """Add a message card to the panel."""
        is_user = (sender.lower() == "you")
        self._msg_count += 1

        card = QWidget()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 12, 20, 12)
        card_layout.setSpacing(6)

        if is_user:
            card.setStyleSheet("""
                QWidget {
                    background: #1C1C20;
                    border-radius: 12px;
                    margin: 2px 8px 2px 8px;
                }
            """)
        else:
            card.setStyleSheet("""
                QWidget {
                    background: transparent;
                    margin: 2px 8px 2px 8px;
                }
            """)

        # Sender label
        sender_lbl = QLabel(sender)
        sender_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        if is_user:
            sender_lbl.setStyleSheet("color: #A1A1AA; background: transparent;")
        else:
            sender_lbl.setStyleSheet("color: #6366f1; background: transparent;")
        card_layout.addWidget(sender_lbl)

        # Message text
        msg_lbl = QLabel(text)
        msg_lbl.setFont(QFont("Segoe UI", 14))
        msg_lbl.setStyleSheet("color: #F5F5F7; background: transparent;")
        msg_lbl.setWordWrap(True)
        msg_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        card_layout.addWidget(msg_lbl)

        self._container_layout.addWidget(card)

        # Scroll to bottom after Qt processes the layout update
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def clear_messages(self) -> None:
        """Remove all message cards."""
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._msg_count = 0
