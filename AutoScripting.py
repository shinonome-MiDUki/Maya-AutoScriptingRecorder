import re
import os
import json
import sys
import shutil
import importlib
import tempfile

from PySide6.QtWidgets import QWidget
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QTimer

from maya.app.general.mayaMixin import MayaQWidgetBaseMixin
from maya import cmds as cmds
from maya import mel as mel 

UI_FILE_PATH = "/Users/shiinaayame/Documents/maya tool/AutoScriptingRecorder/AutoScriptingRecorder/form.ui"

class CustomMayaUI(MayaQWidgetBaseMixin, QWidget):
    def __init__(self, parent=None):
        super(CustomMayaUI, self).__init__(parent=parent)
        
        self.ui = QUiLoader().load(UI_FILE_PATH, self)

        self.operating_mesh = None
        self.path = ""
        self.tempdir = ""
        self.script_name = ""
        self.is_overwrite_confirm = False

        self.ui.start_record_button.clicked.connect(self.start_record_console)
        self.ui.end_record_button.clicked.connect(self.end_record_console)
        self.ui.mel_command_capture_list.itemSelectionChanged.connect(self.show_mel_edit_widget)
        self.ui.generate_script_button.clicked.connect(self.generate_python_script)
        self.ui.set_hotkey_keysequence.setClearButtonEnabled(True)
        self.ui.generate_ui_checkbox.setChecked(False)
        self.ui.save_script_button.clicked.connect(self.save_python_script)
        self.ui.run_script_button.clicked.connect(self.run_script) 
        self.ui.name_script_input_box.textChanged.connect(self.set_script_name)

        self.ui.recordng_label.setText("")
        self.ui.recordng_label.setStyleSheet("color: green")
        self.ui.save_warning_label.setText("")
        self.ui.save_warning_label.setStyleSheet("color: red")
        self.ui.generation_warning_label.setText("")
        self.ui.generation_warning_label.setStyleSheet("color: red")
        self.ui.run_error_label.setText("")
        self.ui.run_error_label.setStyleSheet("color: red")

        self.ui.script_directory_dropdown_box.currentTextChanged.connect(self.script_selection_changed)
        self.ui.delete_script_button.hide()
        self.ui.edit_script_button.hide()
        self.ui.delete_confirmation_widget.hide()
        self.ui.mel_edit_widget.hide()
        
        self.variable_original_value_dict = {}
        self.variable_name_dict = {}
        self.variable_iteration_dict = {}
        self.random_variable_dict = {}
        self.variable_of_line_record_dict = {}

        if not cmds.objExists("autoscripting_node"):
            cmds.createNode("network", n="autoscripting_node")
        if not cmds.objExists("autoscripting_node.autoscripting_data"):
            cmds.addAttr("autoscripting_node", longName="autoscripting_data", dataType="string")
            current_workspace_dir = cmds.workspace(q=True, dir=True)
            data_file_path = os.path.join(current_workspace_dir, "autoscripting_data.json")
            cmds.setAttr("autoscripting_node.autoscripting_data", str(data_file_path), type="string")
        if not cmds.objExists("autoscripting_node.autoscripting_usersetdir"):
            cmds.addAttr("autoscripting_node", longName="autoscripting_usersetdir", dataType="string")
            cmds.setAttr("autoscripting_node.autoscripting_usersetdir", "", type="string")

        userset_dir = str(cmds.getAttr("autoscripting_node.autoscripting_usersetdir"))
        self.ui.script_directory_input_box.setText(userset_dir)

        data_storage_path = cmds.getAttr("autoscripting_node.autoscripting_data")
        self.data_storage_dict = {}
        if os.path.exists(data_storage_path):
            with open(data_storage_path, mode="r", encoding="utf-8") as data_storage:
                self.data_storage_dict = json.load(data_storage)
                self.ui.script_directory_dropdown_box.clear()
                current_existing_scripts = [script_name for script_name in self.data_storage_dict]
                self.ui.script_directory_dropdown_box.addItems(current_existing_scripts)
        else:
            with open(data_storage_path, mode="w", encoding="utf-8") as data_storage:
                json.dump(self.data_storage_dict, data_storage, indent=1)
        
    def start_record_console(self):
        self.tempdir = tempfile.mkdtemp() #テンポラリディレクトリ作成
        self.path = os.path.join(self.tempdir, "hfn_temp.txt") #テンポラリファイルパス作成
        with open(self.path, "w", encoding="utf-8") as f: #テンポラリファイル作成
            pass
        self.ui.recordng_label.setText("Recording Action ...")
        cmds.scriptEditorInfo(hfn=self.path, wh=True) #Mayaのスクリプトエディタの履歴をファイルに書き出し開始

    def process_mel_commands_on_concole(self):
        self.ui.mel_command_capture_list.clear() #リストクリア
        mel_records = [] #メルコマンド格納用リスト
        if not os.path.exists(self.path):
            print("File does not exist")
            return
        with open(self.path, "r", encoding="utf-8") as read_mel_record: #メルコマンド読み込み
            mel_record_raw = read_mel_record.readlines()
        for mel_record in mel_record_raw: #メルコマンド処理
            if mel_record.startswith("import"):
                break #import文以降は無視(実行されたこのツールのスクリプトも記録されているため)
            elif mel_record.startswith("select"):
                continue #selectコマンドは無視(Mayaではselectの誤操作は多い・また、選択はend_recordingの直前の選択に準拠するため)
            else:
                mel_records.append(mel_record.strip("\n")) 
        self.ui.mel_command_capture_list.addItems(mel_records) #リストにメルコマンド追加

    def end_record_console(self):
        try:
            cmds.scriptEditorInfo(hfn=self.path, wh=False) #Mayaのスクリプトエディタの履歴をファイルに書き出し停止
        except Exception as e:
            print(e)
        self.process_mel_commands_on_concole() #メルコマンド処理
        if os.path.exists(self.tempdir):
            shutil.rmtree(self.tempdir) #テンポラリディレクトリ削除
        self.ui.recordng_label.setText("")
        self.ui.generated_python_script_view.setPlainText("")
        self.variable_name_dict.clear()
        self.variable_original_value_dict.clear()
        self.variable_iteration_dict.clear()
        self.random_variable_dict.clear()
        self.variable_of_line_record_dict.clear()
        self.operating_mesh = cmds.ls(sl=True)[0]

    def set_script_name(self):
        self.script_name = self.ui.name_script_input_box.text()

    def script_selection_changed(self):
        selected_script = self.ui.script_directory_dropdown_box.currentText()
        if selected_script != "":
            self.ui.delete_script_button.show()
            self.ui.delete_script_button.clicked.connect(self.show_delete_confirmation_widget)
            self.ui.edit_script_button.show()
            self.ui.edit_script_button.clicked.connect(self.edit_script)
        else:
            self.ui.delete_script_button.hide()
            self.ui.edit_script_button.hide()

    def search_for_potential_variables(self, line):
        variables_ls = re.findall(r"-\w+ [\d|.|\s]+", line)
        return variables_ls

    def show_mel_edit_widget(self):
        selected_line = self.ui.mel_command_capture_list.selectedItems()
        selected_line_index = self.ui.mel_command_capture_list.currentRow()
        if selected_line:
            self.ui.mel_edit_widget.show()
            self.ui.inrange_staticlabel.hide()
            self.ui.random_from_inputbox.hide()
            self.ui.hifen_staticlabel.hide()
            self.ui.random_to_inputbox.hide()
            self.ui.randomize_variable_button.hide()
            self.ui.delete_variable_button.hide()
            self.ui.add_iteration_checkbox.hide()
            self.ui.randomize_warning.setText("")
            self.ui.iteration_widget.hide()
            selected_line_text = str(selected_line[0].text())
            self.ui.edit_mel_input_box.setText(selected_line_text)
            self.ui.update_mel_button.clicked.connect(self.update_mel)
            self.ui.set_to_variable_dropbox.clear()
            self.ui.set_to_variable_dropbox.addItems([str(component) for component in selected_line_text.rstrip(";").split(" ")])
            self.ui.add_to_variable_button.clicked.connect(self.add_to_variable)
            self.ui.variables_list_list.clear()
            if selected_line_index in self.variable_of_line_record_dict:
                self.ui.variables_list_list.addItems(self.variable_of_line_record_dict[selected_line_index])
            self.ui.variables_list_list.itemSelectionChanged.connect(self.when_variable_selected)
            self.ui.addvar_warning_label.setText("")
            self.ui.addvar_warning_label.setStyleSheet("color: red")
        else:
            self.ui.mel_edit_widget.hide()
        
    def update_mel(self):
        self.ui.iteration_widget.hide()
        self.ui.delete_variable_button.hide()
        selected_line = self.ui.mel_command_capture_list.selectedItems() #選択行取得
        selected_line[0].setText(self.ui.edit_mel_input_box.text()) #選択行更新
        selected_line_text = str(selected_line[0].text()) #選択行テキスト取得
        self.ui.set_to_variable_dropbox.clear() 
        self.ui.set_to_variable_dropbox.addItems([str(component) for component in selected_line_text.rstrip(";").split(" ")])  #ドロップダウンリスト更新

    def add_to_variable(self):
        selected_line = self.ui.mel_command_capture_list.selectedItems() #選択したMELコマンドラインのアイテム取得
        selected_line_index = self.ui.mel_command_capture_list.currentRow() #選択したMELコマンドラインのインデックス取得
        selected_line_text = str(selected_line[0].text()) #選択したMELコマンドラインのテキスト取得
        selected_line_component_list = [str(component) for component in selected_line_text.rstrip(";").split(" ")] #選択行コンポーネントリスト作成
        variable_name = self.ui.variable_name_input_box.text() #ユーザの自作変数名取得
        self.ui.variable_name_input_box.setText("")
        if variable_name in self.variable_name_dict:
            self.ui.addvar_warning_label.setText("This variable name is used")
            return
        
        self.variable_original_value_dict[variable_name] = selected_line_text #deleteできるように変数の元の値を保存
        selected_variable = self.ui.set_to_variable_dropbox.currentText() #ユーザが選択した変数化するMELコマンドの部分を取得
        selected_variable_index = self.ui.set_to_variable_dropbox.currentIndex() #ユーザが選択した変数化するMELコマンドの部分のインデックスを取得
        if variable_name == "":
            self.ui.addvar_warning_label.setText("Name your variable")
            return
        
        if selected_line_index not in self.variable_of_line_record_dict:
            self.variable_of_line_record_dict[selected_line_index] = []
        self.variable_of_line_record_dict[selected_line_index].append(variable_name) #MELコマンドラインとそこに設定された変数名を記録
        
        if re.fullmatch(r"-?\d+", selected_variable): #整数判定
            var_type = "int"
            selected_line_component_list[selected_variable_index] = "{" + str(variable_name) + "}"
        elif re.fullmatch(r"-?\d+\.\d+", selected_variable): #浮動小数点数判定
            var_type = "float"
            selected_line_component_list[selected_variable_index] = "{" + str(variable_name) + "}"
        else:
            var_type = "string" #文字列判定
            selected_line_component_list[selected_variable_index] = "-{" + str(variable_name) + "}"

        new_selected_line = " ".join(selected_line_component_list) + ";" #選択行コンポーネントリストを結合して新しい選択行テキスト作成
        selected_line[0].setText(new_selected_line) #MELディスプレイ更新
        self.variable_name_dict[variable_name] = var_type #変数名と型を辞書に保存

        try:
            self.ui.add_to_variable_button.clicked.disconnect(self.add_to_variable)
        except:
            pass
        self.ui.add_to_variable_button.clicked.connect(self.add_to_variable)

        self.ui.addvar_warning_label.setText("")
        self.ui.variables_list_list.addItem(variable_name)
        self.ui.generate_ui_checkbox.setChecked(True)

    def when_variable_selected(self):
        if self.ui.variables_list_list.selectedItems():
            self.ui.delete_variable_button.show()
            self.ui.delete_variable_button.clicked.connect(self.delete_variable)
            selected_variable = self.ui.set_to_variable_dropbox.currentText()
            try:
                selected_variable = float(selected_variable)
                self.ui.add_iteration_checkbox.show()
                self.ui.add_iteration_checkbox.setChecked(False)
                self.ui.add_iteration_checkbox.stateChanged.connect(self.iteration_checkbox_changed)
                self.ui.inrange_staticlabel.show()
                self.ui.random_from_inputbox.show()
                self.ui.random_from_inputbox.setText("0")
                self.ui.hifen_staticlabel.show()
                self.ui.random_to_inputbox.show()
                self.ui.random_to_inputbox.setText("1")
                self.ui.randomize_variable_button.show()
                self.ui.randomize_variable_button.clicked.connect(self.randomize_variable)
                try:
                    self.ui.randomize_variable_button.clicked.disconnect(self.randomize_variable)
                except:
                    pass
                self.ui.randomize_variable_button.clicked.connect(self.randomize_variable)
            except ValueError:
                pass
        else:
            self.ui.delete_variable_button.hide()
            self.ui.add_iteration_checkbox.hide()
            self.ui.iteration_widget.hide()
            self.ui.inrange_staticlabel.hide()
            self.ui.random_from_inputbox.hide()
            self.ui.hifen_staticlabel.hide()
            self.ui.random_to_inputbox.hide()
            self.ui.randomize_variable_button.hide()

    def delete_variable(self):
        selected_line = self.ui.mel_command_capture_list.selectedItems()[0]
        selected_line_index = self.ui.mel_command_capture_list.currentRow()
        item_to_be_deleted = self.ui.variables_list_list.selectedItems()[0]
        item_to_be_deleted_name = item_to_be_deleted.text()
        row_to_be_deleted = self.ui.variables_list_list.row(item_to_be_deleted)
        self.ui.variables_list_list.takeItem(row_to_be_deleted)
        original_line = self.variable_original_value_dict[item_to_be_deleted_name]
        self.ui.mel_command_capture_list.selectedItems()[0].setText(original_line)
        del self.variable_name_dict[item_to_be_deleted_name]
        if item_to_be_deleted_name in self.variable_iteration_dict:
            del self.variable_iteration_dict[item_to_be_deleted_name] 
        if item_to_be_deleted_name in self.random_variable_dict:
            del self.random_variable_dict[item_to_be_deleted_name]
        self.variable_of_line_record_dict[selected_line_index].remove(item_to_be_deleted_name)
        if self.variable_name_dict == {}:
            self.ui.generate_ui_checkbox.setChecked(False)
        try:
            self.ui.delete_variable_button.clicked.disconnect(self.delete_variable)
        except:
            pass
        self.ui.delete_variable_button.clicked.connect(self.delete_variable)

    def randomize_variable(self):
        self.ui.iteration_widget.hide()
        self.ui.add_iteration_checkbox.hide()
        item_to_be_randomized = self.ui.variables_list_list.selectedItems()[0]
        item_to_be_randomized_name = item_to_be_randomized.text()
        random_from = self.ui.random_from_inputbox.text()
        random_to = self.ui.random_to_inputbox.text()
        try:
            random_from = float(random_from)
            random_to = float(random_to)
        except ValueError:
            self.ui.randomize_warning.setText("Input a valid numeric range")
            self.ui.randomize_warning.setStyleSheet("color: red")
            QTimer.singleShot(3000, lambda: self.reset_warning_label(self.ui.randomize_warning))
            return
        self.ui.randomize_warning.setText("Variable randomized")
        self.ui.randomize_warning.setStyleSheet("color: #98FBCB")
        QTimer.singleShot(3000, lambda: self.reset_warning_label(self.ui.randomize_warning))
        self.random_variable_dict[item_to_be_randomized_name] = f"{random_from}, {random_to}"

    def iteration_checkbox_changed(self):
        if self.ui.add_iteration_checkbox.isChecked():
            self.ui.iteration_widget.show()
            self.ui.set_iteration_button.clicked.connect(self.set_iteration)
            self.ui.delete_iteration_button.clicked.connect(self.delete_iteration)
            self.ui.init_value_input_box.setText("1")
            self.ui.calculation_operator_dropdown.clear()
            self.ui.calculation_operator_dropdown.addItems(["+", "-", "*", "/"])
            self.ui.iteration_warning_label.setText("")
            self.ui.iteration_warning_label.setStyleSheet("color: red")
        else:
            self.ui.iteration_widget.hide()

    def set_iteration(self):
        calculation_operator = self.ui.calculation_operator_dropdown.currentText() #演算子取得
        selected_variable_name = self.ui.variables_list_list.selectedItems()[0].text() #変数名取得
        try: 
            init_value = float(self.ui.init_value_input_box.text()) #初期値取得
            if self.ui.allow_python_expression_checkbox.isChecked():   #Python式として扱う場合かどうか
                iteration_const = self.ui.iteration_const_input_box.text() 
            else:
                iteration_const = float(self.ui.iteration_const_input_box.text()) 
            self.ui.iteration_warning_label.setText("")
        except ValueError:
            self.ui.iteration_warning_label.setText("Only numeric value allowed")
            return
        iteration_expression = f"{init_value} + (i {calculation_operator} {iteration_const})" #イテレーション式作成
        self.variable_iteration_dict[selected_variable_name] = iteration_expression #辞書に保存
        self.ui.iteration_warning_label.setText("Add iteration successful")
        self.ui.iteration_warning_label.setStyleSheet("color: #98FBCB")
        QTimer.singleShot(3000, lambda: self.reset_warning_label(self.ui.iteration_warning_label))

    def delete_iteration(self):
        selected_variable_name = self.ui.variables_list_list.selectedItems()[0].text()
        if selected_variable_name in self.variable_iteration_dict:
            del self.variable_iteration_dict[selected_variable_name]

    def generate_python_fucntion(self):
        python_script_ls = []
        generated_nodes = []
        generated_node_index = 0
        mel_records_obj = self.ui.mel_command_capture_list
        mel_records = [mel_records_obj.item(idx).text() for idx in range(0, mel_records_obj.count())]
        for mel_command in mel_records:
            if mel_command == "": 
                continue
            elif mel_command.startswith("// "):
                mel_command = mel_command.lstrip("// ")
                newly_generated_node = mel_command
                generated_nodes.append(newly_generated_node)
                python_script_ls[-1] = f"new_node_{generated_node_index} = " + python_script_ls[-1]
                generated_node_index += 1
            else:
                if generated_nodes: #生成されたノードがある場合、メルコマンド内のノード名を置換
                    i = 0
                    while i < len(generated_nodes):
                        generated_node = generated_nodes[i]
                        if generated_node in mel_command: 
                            mel_command = mel_command.replace(generated_node, "{new_node_" + str(i) + "[0]}") #変数に置換
                        i += 1
                if self.operating_mesh in mel_command: #操作対象メッシュ名を変数に置換  
                    mel_command = mel_command.replace(self.operating_mesh, "{" + "obj}")
                if "\"" in mel_command:  #ダブルクオーテーションが含まれる場合、エスケープ処理  
                    mel_command = mel_command.replace("\"", "\\\"")
                python_command = f"mel.eval(f\"{mel_command}\")" #メルコマンドをPythonコードに変換
                python_script_ls.append(python_command)
        return python_script_ls
    
    def write_py(self, py, indentaion):
        self.ui.generated_python_script_view.appendPlainText("    " * indentaion + py)

    def generate_python_script_noui(self):
        python_script_ls = self.generate_python_fucntion()
        self.ui.generated_python_script_view.setPlainText("from maya import mel as mel")
        if self.random_variable_dict:
            self.write_py("import random")
        self.write_py("", 0)
        if self.variable_iteration_dict:
            self.write_py("def operation(i, obj):", 0)
        else:
            self.write_py("def operation(obj):", 0)
        for variable in self.variable_iteration_dict:
            self.write_py(f"{variable} = {self.variable_iteration_dict[variable]}", 1)
        for variable in self.random_variable_dict:
            self.write_py(f"{variable} = random.uniform({self.random_variable_dict[variable]})", 1)
        self.write_py("", 1)
        for python_line in python_script_ls:
            self.write_py(python_line, 1)
        self.write_py("", 0)
        self.write_py("def main():", 0)
        self.write_py("selected_objects = cmds.ls(selection=True)", 1)
        self.write_py("if selected_objects:", 1)
        self.write_py("for obj in selected_objects:", 2)
        if self.variable_iteration_dict:
            self.write_py("i = selected_objects.index(obj)", 3)
        self.write_py("cmds.select(obj, replace=True)", 3)
        if self.variable_iteration_dict:
            self.write_py("operation(i, obj)", 3) 
        else:
            self.write_py("operation(obj)", 3) 
        self.write_py("", 0)
        self.write_py("main()", 0)

    def generate_python_script_wui(self):
        python_script_ls = self.generate_python_fucntion()
        self.ui.generated_python_script_view.setPlainText("from maya import cmds as cmds")
        self.write_py("from maya import mel as mel", 0)
        if self.random_variable_dict:
            self.write_py("import random", 0)
        self.write_py("", 0)
        self.write_py("def main(*args):", 0)
        if self.variable_iteration_dict:
            self.write_py("def operation(i, obj):", 1)
        else:
            self.write_py("def operation(obj):", 1)
        for variable in self.variable_name_dict:
            if variable not in self.variable_iteration_dict and variable not in self.random_variable_dict:
                self.write_py(f"{variable} = {self.variable_name_dict[variable]}(cmds.textField(\"{variable}\", q=True, text=True))", 2)
            else:
                if variable in self.variable_iteration_dict:
                    self.write_py(f"{variable} = {self.variable_iteration_dict[variable]}", 2)
                elif variable in self.random_variable_dict:
                    self.write_py(f"{variable} = random.uniform({self.random_variable_dict[variable]})", 2)
        for python_line in python_script_ls:
            self.write_py(python_line, 2)
        self.write_py("", 1)
        self.write_py("def myfunction(*args):", 1)
        self.write_py("selected_objects = cmds.ls(selection=True)", 2)
        self.write_py("if selected_objects:", 2)
        self.write_py("for obj in selected_objects:", 3)
        if self.variable_iteration_dict:
            self.write_py("i = selected_objects.index(obj)", 4)
        self.write_py("cmds.select(obj, replace=True)", 4)
        if self.variable_iteration_dict:
            self.write_py("operation(i, obj)", 4) 
        else:
            self.write_py("operation(obj)", 4) 
        self.write_py("", 1)
        self.write_py(f"title = \"{self.script_name}\"", 1)
        self.write_py("if cmds.window(title, exists=True):", 1)
        self.write_py("cmds.deleteUI(title)", 2)
        self.write_py("GUI = cmds.window(title, title=title, w=450, h=430, s=True)", 1)
        self.write_py(f"cmds.columnLayout(columnAttach=('both', {1+len(self.variable_name_dict)}), rowSpacing=10, columnWidth=500)", 1)
        self.write_py("", 1)
        self.write_py("cmds.rowLayout(nc=2, cw2=[100,100])", 1)
        self.write_py("cmds.text(\" \")", 1)
        self.write_py("cmds.button(label=\"Run\", c=myfunction, width=100)", 1)
        self.write_py("cmds.setParent(\"..\")", 1)
        self.write_py("", 1)
        if self.variable_name_dict != {}:
            for variable in self.variable_name_dict:
                if variable not in self.variable_iteration_dict and variable not in self.random_variable_dict:
                    self.write_py("cmds.rowLayout(nc=2, cw2=[100,100])", 1)
                    self.write_py(f"cmds.text(\"{variable}\")", 1)
                    self.write_py(f"cmds.textField(\"{variable}\", text=None, w=100)", 1)
                    self.write_py("cmds.setParent(\"..\")", 1)
        self.write_py("", 1)
        self.write_py("cmds.showWindow(GUI)", 1)
        self.write_py("", 0)
        self.write_py("main()", 0)

    def generate_python_script(self):
        self.script_name = self.ui.name_script_input_box.text()
        if self.script_name == "":
            self.ui.generation_warning_label.setText("Name your script")
            return
        if self.ui.generate_ui_checkbox.isChecked():
            if self.variable_iteration_dict or self.random_variable:
                self.ui.generation_warning_label.setText("Note that randomized and iterating variables cannot be set from UI")
            self.ui.generation_warning_label.setText("")
            self.generate_python_script_wui()
        else:
            if self.variable_name_dict:
                self.ui.generation_warning_label.setText("Scripts with variables must be generated under UI mode")
                return
            self.ui.generation_warning_label.setText("")
            self.generate_python_script_noui()

    def store_data(self, script_name, save_dir):
        data_storage_path = cmds.getAttr("autoscripting_node.autoscripting_data")
        with open(data_storage_path, "r") as data_storage:
            self.data_storage_dict = json.load(data_storage)
        self.data_storage_dict[script_name] = save_dir
        with open(data_storage_path, "w") as data_storage:
            json.dump(self.data_storage_dict, data_storage, indent=1)
        current_existing_scripts = [script_name for script_name in self.data_storage_dict]
        current_existing_scripts = list(set(current_existing_scripts))
        self.ui.script_directory_dropdown_box.clear()
        self.ui.script_directory_dropdown_box.addItems(current_existing_scripts)


    def save_python_script(self):
        save_dir = self.ui.script_directory_input_box.text()
        script_name = self.script_name
        if save_dir == "":
            self.ui.save_warning_label.setText("Please designate a directory")
            return
        if not os.path.exists(save_dir):
            self.ui.save_warning_label.setText("Designated directory does not exist")
            return
        save_path = os.path.join(save_dir, f"{script_name}.py")
        data_storage_path = cmds.getAttr("autoscripting_node.autoscripting_data")
        with open(data_storage_path, "r") as data_storage:
            self.data_storage_dict = json.load(data_storage)
        if script_name == "":
            self.ui.save_warning_label.setText("Name your script")
            return
        if script_name in sys.stdlib_module_names or script_name in sys.builtin_module_names:
            self.ui.save_warning_label.setText("Script name overlapping with standard library")
            return  
        if script_name in self.data_storage_dict:
            if not self.is_overwrite_confirm:
                self.ui.save_warning_label.setText("Script with the same name already exists. Ckick Save again to overwrite.")
                self.is_overwrite_confirm = True
                return
            else:
                self.is_overwrite_confirm = False
                if os.path.exists(save_path):
                    os.unlink(save_path)
                del self.data_storage_dict[script_name]
        python_script_generated = self.ui.generated_python_script_view.toPlainText()
        with open(save_path, "w", encoding="utf-8") as py_file:
            py_file.write(python_script_generated)
        self.store_data(script_name, save_dir)
        self.ui.save_warning_label.setText("Saved successfully")
        self.ui.save_warning_label.setStyleSheet("color: #98FBCB")
        cmds.setAttr("autoscripting_node.autoscripting_usersetdir", str(save_dir), type="string")
        self.is_overwrite_confirm = False
        QTimer.singleShot(3000, lambda: self.reset_warning_label(self.ui.save_warning_label))

    def reset_warning_label(self, warning_label_obj):
        warning_label_obj.setText("")
        warning_label_obj.setStyleSheet("color: red")

    def run_script(self):
        data_storage_path = cmds.getAttr("autoscripting_node.autoscripting_data") #データ保存パス取得
        with open(data_storage_path) as data_storage:
            self.data_storage_dict = json.load(data_storage) #データ保存ファイル読み込み
        selected_script = self.ui.script_directory_dropdown_box.currentText()
        selected_script_dir = self.data_storage_dict[selected_script]
        selected_script_path = os.path.join(selected_script_dir, f"{selected_script}.py") #スクリプトパス作成
        if not os.path.exists(selected_script_path): #スクリプトパス存在確認
            self.ui.run_error_label.setText("Script does not exist")
            return
        if selected_script_dir not in sys.path: #スクリプトディレクトリがsys.pathに存在しない場合追加
            sys.path.insert(0,selected_script_dir)
        module_name = selected_script
        try:
            if module_name in sys.modules: 
                del sys.modules[module_name] #既にインポートされている場合は削除して再インポート
            module = importlib.import_module(self.script_name)

            module.main()
        except ImportError:
            self.ui.run_error_label.setText("ImportError. Cannot find module")
        except Exception as e:
            self.ui.run_error_label.setText(f"Python error : {str(e)}")
            print(e)
            print("module" + module_name)

    def show_delete_confirmation_widget(self):
        self.ui.delete_confirmation_widget.show()
        self.ui.confirmation_msg_label.setStyleSheet("color: red")
        selected_script = self.ui.script_directory_dropdown_box.currentText()
        self.ui.dir_to_delete_label.setText(os.path.join(self.data_storage_dict[selected_script], f"{selected_script}.py"))
        self.ui.dir_to_delete_label.setStyleSheet("color: red")
        self.ui.yes_delete_button.clicked.connect(self.delete_script)
        self.ui.no_delete_button.clicked.connect(self.hide_delete_confirmation_widget)

    def hide_delete_confirmation_widget(self):
        self.ui.delete_confirmation_widget.hide()

    def delete_script(self):
        selected_script = self.ui.script_directory_dropdown_box.currentText()
        selected_script_path = os.path.join(self.data_storage_dict[selected_script], f"{selected_script}.py")
        if os.path.exists(selected_script_path):
            os.unlink(selected_script_path)
        del self.data_storage_dict[selected_script]
        data_storage_path = cmds.getAttr("autoscripting_node.autoscripting_data")
        with open(data_storage_path, "w") as data_storage:
            json.dump(self.data_storage_dict, data_storage, indent=1)
        row_to_be_deleted = self.ui.script_directory_dropdown_box.currentIndex()
        self.ui.script_directory_dropdown_box.removeItem(row_to_be_deleted)
        self.hide_delete_confirmation_widget()

    def edit_script(self):
        selected_script = self.ui.script_directory_dropdown_box.currentText()
        selected_script_path = os.path.join(self.data_storage_dict[selected_script], f"{selected_script}.py")
        if not os.path.exists(selected_script_path):
            self.ui.run_error_label.setText("Script does not exist")
            return
        with open(selected_script_path, "r", encoding="utf-8") as script_file:
            script_content = script_file.read()
        self.ui.script_directory_input_box.setText(self.data_storage_dict[selected_script])
        self.ui.name_script_input_box.setText(selected_script)
        self.ui.generated_python_script_view.setPlainText(script_content)

def show_ui():
    global my_window
    try:
        my_window.close() 
    except:
        pass
    
    my_window = CustomMayaUI()
    my_window.show()
    
show_ui()