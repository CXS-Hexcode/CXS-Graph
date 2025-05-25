import sys
import csv
import json
import os
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QDialog, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QPushButton, QHBoxLayout,
    QDialogButtonBox, QMainWindow, QToolBar, QLabel, QVBoxLayout
)
from PyQt5.QtCore import Qt


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots(figsize=(10, 6), dpi=100)
        super().__init__(self.fig)
        self.setParent(parent)

        self.fig.patch.set_facecolor("#1e1e1e")
        self.ax.set_facecolor("#1e1e1e")
        self.ax.axis('off')

        self.node_positions = {}
        self.graph = None
        self.scale = 1.0

        self.fig.canvas.mpl_connect('scroll_event', self.zoom)
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)

    def update_graph(self, G, pos, measure=None):
        self.ax.clear()
        self.graph = G
        self.node_positions = pos

        self.fig.patch.set_facecolor("#1e1e1e")
        self.ax.set_facecolor("#1e1e1e")
        self.ax.axis('off')

        type_colors = {
            "email": "#E91E63",
            "ip": "#3F51B5",
            "nom": "#4CAF50",
            "autre": "#9E9E9E"
        }
        base_colors = [
            type_colors.get(G.nodes[n].get("type", "autre"), "#9E9E9E")
            for n in G.nodes
        ]

        if measure:
            vals = list(measure.values())
            if vals:
                min_val, max_val = min(vals), max(vals)
            else:
                min_val = max_val = 0
            range_val = max_val - min_val if max_val != min_val else 1
            sizes = [
                300 + 3000 * (measure.get(n, 0) - min_val) / range_val
                for n in G.nodes
            ]
            colors = []
            for n in G.nodes:
                norm = (measure.get(n, 0) - min_val) / range_val
                base_color = QtGui.QColor(base_colors[list(G.nodes).index(n)])
                r, g, b, _ = base_color.getRgb()
                r = int(r + (255 - r) * norm)
                g = int(g + (255 - g) * norm)
                b = int(b + (255 - b) * norm)
                colors.append(f"#{r:02x}{g:02x}{b:02x}")
        else:
            sizes = [800] * len(G.nodes)
            colors = base_colors

        nx.draw_networkx_edges(G, pos, ax=self.ax, edge_color="#888", alpha=0.7)
        nx.draw_networkx_nodes(
            G, pos, ax=self.ax,
            node_color=colors,
            node_size=sizes,
            edgecolors='white',
            linewidths=1.5
        )
        nx.draw_networkx_labels(
            G, pos, ax=self.ax,
            font_color='white',
            font_size=11,
            font_weight='bold'
        )
        self.fig.tight_layout()
        self.draw()

    def zoom(self, event):
        base_scale = 1.2
        if event.button == 'up':
            scale_factor = base_scale
        elif event.button == 'down':
            scale_factor = 1 / base_scale
        else:
            return

        self.scale *= scale_factor
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        xdata = event.xdata
        ydata = event.ydata
        if xdata is None or ydata is None:
            return

        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0]) if (cur_xlim[1] - cur_xlim[0]) != 0 else 0.5
        rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0]) if (cur_ylim[1] - cur_ylim[0]) != 0 else 0.5

        self.ax.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * relx])
        self.ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])
        self.draw()

    def on_click(self, event):
        if event.inaxes != self.ax:
            return
        x_click, y_click = event.xdata, event.ydata
        tolerance = 0.05
        if self.graph is None or not self.node_positions:
            return

        for node, (x_node, y_node) in self.node_positions.items():
            if abs(x_node - x_click) < tolerance and abs(y_node - y_click) < tolerance:
                self.show_node_info(node)
                break

    def show_node_info(self, node):
        data = self.graph.nodes[node]
        dlg = QDialog()
        dlg.setWindowTitle(f"Infos sur le nœud '{node}'")
        dlg.setModal(True)
        dlg.resize(400, 400)
        layout = QFormLayout(dlg)

        layout.addRow("Valeur:", QLabel(node))
        for field in ["type", "url", "description"]:
            val = data.get(field, "")
            if val:
                lbl = QLabel(val)
                lbl.setWordWrap(True)
                layout.addRow(f"{field.capitalize()}:", lbl)

        img_path = data.get("image", "")
        if img_path and os.path.isfile(img_path):
            pixmap = QtGui.QPixmap(img_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaledToWidth(200, QtCore.Qt.SmoothTransformation)
                img_label = QLabel()
                img_label.setPixmap(pixmap)
                img_label.setAlignment(Qt.AlignCenter)
                layout.addRow("Image:", img_label)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec_()


class NodeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter un Nœud")
        self.setModal(True)
        self.resize(400, 320)

        layout = QFormLayout(self)

        self.fields = {
            "value": QLineEdit(),
            "type": QComboBox(),
            "url": QLineEdit(),
            "description": QTextEdit(),
            "image": QLineEdit()
        }

        self.fields["type"].addItems(["nom", "email", "ip", "autre"])
        self.fields["description"].setFixedHeight(70)

        layout.addRow("Valeur *:", self.fields["value"])
        layout.addRow("Type:", self.fields["type"])
        layout.addRow("URL:", self.fields["url"])
        layout.addRow("Description:", self.fields["description"])

        hbox = QHBoxLayout()
        browse_btn = QPushButton("Parcourir")
        browse_btn.clicked.connect(self.browse_image)
        self.fields["image"].setPlaceholderText("Chemin de l'image...")
        hbox.addWidget(self.fields["image"])
        hbox.addWidget(browse_btn)
        layout.addRow("Image:", hbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir image", "",
            "Images (*.png *.jpg *.bmp *.gif *.jpeg)"
        )
        if path:
            self.fields["image"].setText(path)

    def validate_and_accept(self):
        value = self.fields["value"].text().strip()
        if not value:
            QMessageBox.warning(self, "Erreur", "Le champ 'Valeur' est obligatoire.")
            return
        self.accept()

    def get_data(self):
        data = {}
        for k, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                data[k] = widget.text().strip()
            elif isinstance(widget, QTextEdit):
                data[k] = widget.toPlainText().strip()
            elif isinstance(widget, QComboBox):
                data[k] = widget.currentText()
            else:
                data[k] = None
        return data


class OSINTApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧠OSINT Graph CXS")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #121212; color: white;")

        self.G = nx.Graph()
        self.pos = {}
        self.layout_func = nx.spring_layout

        self.canvas = MplCanvas(self)
        self.setCentralWidget(self.canvas)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Recherche de nœud...")
        self.search_bar.textChanged.connect(self.dynamic_search)

        self.toolbar = QToolBar("Actions")
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        self.toolbar.addWidget(self.search_bar)

        self.init_toolbar_buttons()
        self.init_menu()

        self.current_measure = None 

    def init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Fichier")
        graph_menu = menubar.addMenu("Graphe")

        file_actions = {
            "Nouveau": self.new_graph,
            "Importer CSV": self.import_csv,
            "Exporter CSV": self.export_csv,
            "Charger JSON": self.load_graph_json,
            "Sauvegarder JSON": self.save_graph_json,
            "Quitter": self.close
        }
        for name, func in file_actions.items():
            action = QtWidgets.QAction(name, self)
            action.triggered.connect(func)
            file_menu.addAction(action)

        graph_actions = {
            "Ajouter nœud": self.add_node,
            "Relier nœuds": self.link_nodes,
            "Supprimer nœud": self.remove_node,
            "Supprimer arête": self.remove_edge,
            "Vider liens": self.clear_edges,
            "Degré": self.calculate_degree,
            "Coefficient de clustering": self.calculate_clustering,
            "PageRank": self.calculate_pagerank,
            "Filtrer par type": self.filter_by_type,
            "Changer disposition": self.change_layout
        }
        for name, func in graph_actions.items():
            action = QtWidgets.QAction(name, self)
            action.triggered.connect(func)
            graph_menu.addAction(action)

    def init_toolbar_buttons(self):
        buttons = {
            "➕ Ajouter": self.add_node,
            "🔗 Relier": self.link_nodes,
            "🗑 Supprimer": self.remove_node,
            "❌ Supprimer arrête": self.remove_edge,
            "🧹 Vider liens": self.clear_edges,
            "🔢 Degré": self.calculate_degree,
            "🔄 Clustering": self.calculate_clustering,
            "🌐 PageRank": self.calculate_pagerank
        }
        for name, func in buttons.items():
            btn = QtWidgets.QPushButton(name)
            btn.clicked.connect(func)
            self.toolbar.addWidget(btn)

    def new_graph(self):
        self.G.clear()
        self.pos.clear()
        self.canvas.update_graph(self.G, self.pos)
        self.current_measure = None

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer CSV", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.G.clear()
                for row in reader:
                    src = row.get('source')
                    tgt = row.get('target')
                    if src and tgt:
                        self.G.add_node(src)
                        self.G.add_node(tgt)
                        self.G.add_edge(src, tgt)
            self.pos = self.layout_func(self.G)
            self.canvas.update_graph(self.G, self.pos)
            self.current_measure = None
        except Exception as e:
            QMessageBox.warning(self, "Erreur import CSV", str(e))

    def export_csv(self):
        if self.G.number_of_edges() == 0:
            QMessageBox.warning(self, "Erreur", "Le graphe ne contient aucune arête.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter CSV", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["source", "target"])
                for u, v in self.G.edges():
                    writer.writerow([u, v])
        except Exception as e:
            QMessageBox.warning(self, "Erreur export CSV", str(e))

    def save_graph_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Sauvegarder JSON", "", "JSON files (*.json)")
        if not path:
            return
        try:
            data = nx.node_link_data(self.G)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Erreur sauvegarde JSON", str(e))

    def load_graph_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Charger JSON", "", "JSON files (*.json)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.G = nx.node_link_graph(data)
            self.pos = self.layout_func(self.G)
            self.canvas.update_graph(self.G, self.pos)
            self.current_measure = None
        except Exception as e:
            QMessageBox.warning(self, "Erreur chargement JSON", str(e))


    def add_node(self):
        dlg = NodeDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            val = data["value"]
            if val in self.G:
                QMessageBox.warning(self, "Erreur", f"Le nœud '{val}' existe déjà.")
                return
            self.G.add_node(val, **data)
            self.pos = self.layout_func(self.G)
            self.canvas.update_graph(self.G, self.pos)
            self.current_measure = None

    def link_nodes(self):
        if len(self.G.nodes) < 2:
            QMessageBox.warning(self, "Erreur", "Il faut au moins 2 nœuds pour créer une arrête.")
            return
        nodes = list(self.G.nodes)
        src, ok1 = QInputDialog.getItem(self, "Noeud source", "Choisir le nœud source :", nodes, 0, False)
        if not ok1:
            return
        tgt, ok2 = QInputDialog.getItem(self, "Noeud cible", "Choisir le nœud cible :", nodes, 0, False)
        if not ok2:
            return
        if src == tgt:
            QMessageBox.warning(self, "Erreur", "Un nœud ne peut pas être relié à lui-même.")
            return
        if self.G.has_edge(src, tgt):
            QMessageBox.information(self, "Info", "L'arête existe déjà.")
            return
        self.G.add_edge(src, tgt)
        self.pos = self.layout_func(self.G)
        self.canvas.update_graph(self.G, self.pos)
        self.current_measure = None

    def remove_node(self):
        if not self.G.nodes:
            QMessageBox.warning(self, "Erreur", "Aucun nœud à supprimer.")
            return
        nodes = list(self.G.nodes)
        node, ok = QInputDialog.getItem(self, "Supprimer nœud", "Choisir un nœud :", nodes, 0, False)
        if ok and node:
            self.G.remove_node(node)
            self.pos = self.layout_func(self.G)
            self.canvas.update_graph(self.G, self.pos)
            self.current_measure = None

    def remove_edge(self):
        if not self.G.edges:
            QMessageBox.warning(self, "Erreur", "Aucune arête à supprimer.")
            return
        edges = [f"{u} -- {v}" for u, v in self.G.edges]
        edge_str, ok = QInputDialog.getItem(self, "Supprimer arête", "Choisir une arête :", edges, 0, False)
        if ok and edge_str:
            u, v = edge_str.split(" -- ")
            if self.G.has_edge(u, v):
                self.G.remove_edge(u, v)
                self.pos = self.layout_func(self.G)
                self.canvas.update_graph(self.G, self.pos)
                self.current_measure = None

    def clear_edges(self):
        self.G.remove_edges_from(list(self.G.edges))
        self.pos = self.layout_func(self.G)
        self.canvas.update_graph(self.G, self.pos)
        self.current_measure = None

    def calculate_degree(self):
        if not self.G.nodes:
            QMessageBox.warning(self, "Erreur", "Le graphe est vide.")
            return
        deg = dict(self.G.degree())
        self.current_measure = deg
        self.canvas.update_graph(self.G, self.pos, measure=deg)
        self.show_analysis("Degré", deg)

    def calculate_clustering(self):
        if not self.G.nodes:
            QMessageBox.warning(self, "Erreur", "Le graphe est vide.")
            return
        clustering = nx.clustering(self.G)
        self.current_measure = clustering
        self.canvas.update_graph(self.G, self.pos, measure=clustering)
        self.show_analysis("Coefficient de clustering", clustering)

    def calculate_pagerank(self):
        if not self.G.nodes:
            QMessageBox.warning(self, "Erreur", "Le graphe est vide.")
            return
        pagerank = nx.pagerank(self.G)
        self.current_measure = pagerank
        self.canvas.update_graph(self.G, self.pos, measure=pagerank)
        self.show_analysis("PageRank", pagerank)

    def filter_by_type(self):
        types = set(nx.get_node_attributes(self.G, "type").values())
        if not types:
            QMessageBox.information(self, "Info", "Aucun type trouvé dans les nœuds.")
            return
        types = sorted(list(types))
        types.insert(0, "Tous")
        typ, ok = QInputDialog.getItem(self, "Filtrer par type", "Sélectionner un type :", types, 0, False)
        if ok:
            if typ == "Tous":
                self.pos = self.layout_func(self.G)
                self.canvas.update_graph(self.G, self.pos, measure=self.current_measure)
            else:
                filtered_nodes = [n for n, d in self.G.nodes(data=True) if d.get("type") == typ]
                subg = self.G.subgraph(filtered_nodes)
                self.pos = self.layout_func(subg)
                self.canvas.update_graph(subg, self.pos)

    def change_layout(self):
        layouts = {
            "Spring": nx.spring_layout,
            "Circular": nx.circular_layout,
            "Shell": nx.shell_layout,
            "Spectral": nx.spectral_layout,
            "Random": nx.random_layout
        }
        keys = list(layouts.keys())
        choice, ok = QInputDialog.getItem(self, "Changer disposition", "Choisir une disposition :", keys, 0, False)
        if ok and choice:
            self.layout_func = layouts[choice]
            self.pos = self.layout_func(self.G)
            self.canvas.update_graph(self.G, self.pos, measure=self.current_measure)

    def dynamic_search(self, text):
        text = text.lower()
        matched_nodes = [n for n in self.G.nodes if text in n.lower()]
        if not matched_nodes:
            self.canvas.update_graph(self.G, self.pos, measure=self.current_measure)
            return
        subg = self.G.subgraph(matched_nodes)
        pos = {n: self.pos.get(n, (0, 0)) for n in subg.nodes}
        self.canvas.update_graph(subg, pos, measure=None)

    def show_analysis(self, title, measure):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Analyse : {title}")
        dlg.resize(300, 400)
        layout = QVBoxLayout(dlg)

        text = QTextEdit()
        text.setReadOnly(True)

        sorted_measures = sorted(measure.items(), key=lambda x: x[1], reverse=True)
        lines = [f"{node}: {value:.4f}" if isinstance(value, float) else f"{node}: {value}" for node, value in sorted_measures]
        text.setText("\n".join(lines))

        layout.addWidget(text)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec_()


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = OSINTApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
