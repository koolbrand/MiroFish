"""
项目上下文管理
用于在服务端持久化项目状态，避免前端在接口间传递大量数据
"""

import os
import json
import threading
import uuid
import shutil
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from ..config import Config
from ..utils.security import validate_storage_id, is_valid_storage_id
from ..utils.fs import atomic_write_json, atomic_write_text, read_json_or_none
from ..utils.logger import get_logger

logger = get_logger('mirofish.project')


class ProjectStatus(str, Enum):
    """项目状态"""
    CREATED = "created"              # 刚创建，文件已上传
    ONTOLOGY_GENERATED = "ontology_generated"  # 本体已生成
    GRAPH_BUILDING = "graph_building"    # 图谱构建中
    GRAPH_COMPLETED = "graph_completed"  # 图谱构建完成
    FAILED = "failed"                # 失败


# Marca «usa el dueño de la petición en curso» (distinta de None, que significa «sin dueño»)
_CURRENT_OWNER: Any = object()


@dataclass
class Project:
    """项目数据模型"""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: str
    updated_at: str
    
    # 文件信息
    files: List[Dict[str, str]] = field(default_factory=list)  # [{filename, path, size}]
    total_text_length: int = 0
    
    # 本体信息（接口1生成后填充）
    ontology: Optional[Dict[str, Any]] = None
    analysis_summary: Optional[str] = None
    
    # 图谱信息（接口2完成后填充）
    graph_id: Optional[str] = None
    graph_build_task_id: Optional[str] = None
    
    # 配置
    simulation_requirement: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # 错误信息
    error: Optional[str] = None

    # Investigación en internet (paso opcional antes de la ontología). Sin el
    # Markdown: el documento vive en files/investigacion-internet.md.
    web_research: Optional[Dict[str, Any]] = None

    # Usuario de PocketBase que lo creó (aislamiento por usuario). None = sin dueño: solo lo ve el admin.
    owner_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": self.files,
            "total_text_length": self.total_text_length,
            "ontology": self.ontology,
            "analysis_summary": self.analysis_summary,
            "graph_id": self.graph_id,
            "graph_build_task_id": self.graph_build_task_id,
            "simulation_requirement": self.simulation_requirement,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "error": self.error,
            "web_research": self.web_research,
            "owner_id": self.owner_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """从字典创建"""
        status = data.get('status', 'created')
        if isinstance(status, str):
            status = ProjectStatus(status)
        
        return cls(
            project_id=data['project_id'],
            name=data.get('name', 'Unnamed Project'),
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            files=data.get('files', []),
            total_text_length=data.get('total_text_length', 0),
            ontology=data.get('ontology'),
            analysis_summary=data.get('analysis_summary'),
            graph_id=data.get('graph_id'),
            graph_build_task_id=data.get('graph_build_task_id'),
            simulation_requirement=data.get('simulation_requirement'),
            chunk_size=data.get('chunk_size', 500),
            chunk_overlap=data.get('chunk_overlap', 50),
            error=data.get('error'),
            web_research=data.get('web_research'),
            owner_id=data.get('owner_id')
        )


class ProjectManager:
    """项目管理器 - 负责项目的持久化存储和检索"""
    
    # 项目存储根目录
    PROJECTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'projects')
    
    @classmethod
    def _ensure_projects_dir(cls):
        """确保项目目录存在"""
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_project_dir(cls, project_id: str) -> str:
        """获取项目目录路径"""
        validate_storage_id(project_id, "proj_")
        return os.path.join(cls.PROJECTS_DIR, project_id)
    
    @classmethod
    def _get_project_meta_path(cls, project_id: str) -> str:
        """获取项目元数据文件路径"""
        return os.path.join(cls._get_project_dir(project_id), 'project.json')
    
    @classmethod
    def _get_project_files_dir(cls, project_id: str) -> str:
        """获取项目文件存储目录"""
        return os.path.join(cls._get_project_dir(project_id), 'files')
    
    @classmethod
    def _get_project_text_path(cls, project_id: str) -> str:
        """获取项目提取文本存储路径"""
        return os.path.join(cls._get_project_dir(project_id), 'extracted_text.txt')
    
    @classmethod
    def create_project(cls, name: str = "Unnamed Project", owner_id: Optional[str] = _CURRENT_OWNER) -> Project:
        """
        创建新项目
        
        Args:
            name: 项目名称
            owner_id: dueño (usuario de PocketBase). Por defecto, el de la petición en curso; None = sin dueño
            
        Returns:
            新创建的Project对象
        """
        if owner_id is _CURRENT_OWNER:
            from ..utils.access import current_owner_id
            owner_id = current_owner_id()
        cls._ensure_projects_dir()
        
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        
        project = Project(
            project_id=project_id,
            name=name,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now,
            owner_id=owner_id
        )
        
        # 创建项目目录结构
        project_dir = cls._get_project_dir(project_id)
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        
        # 保存项目元数据
        cls.save_project(project)
        
        return project
    
    # Un candado por proyecto: leer-modificar-escribir sin él pierde cambios cuando dos hilos tocan el mismo
    # proyecto (un hilo largo guardaba su copia vieja encima de un cambio de nombre o de dueño hecho entretanto)
    _locks: Dict[str, threading.RLock] = {}
    _locks_guard = threading.Lock()

    @classmethod
    def lock_for(cls, project_id: str) -> threading.RLock:
        validate_storage_id(project_id, "proj_")
        with cls._locks_guard:
            lock = cls._locks.get(project_id)
            if lock is None:
                lock = cls._locks[project_id] = threading.RLock()
            return lock

    @classmethod
    def save_project(cls, project: Project) -> None:
        """Guarda los metadatos de forma atómica. Falla (FileNotFoundError) si el proyecto ya no existe:
        un hilo que sigue vivo no debe resucitar un proyecto borrado."""
        with cls.lock_for(project.project_id):
            project.updated_at = datetime.now().isoformat()
            atomic_write_json(cls._get_project_meta_path(project.project_id), project.to_dict(), create_dir=False)

    @classmethod
    def update_project(cls, project_id: str, mutator: Callable[[Project], None]) -> Optional[Project]:
        """
        Cambia SOLO lo que toca `mutator` sobre la copia más reciente del disco. Los hilos largos usan esto en
        vez de guardar el objeto que leyeron al empezar. None si el proyecto no existe (o está ilegible).
        """
        with cls.lock_for(project_id):
            project = cls.get_project(project_id)
            if project is None:
                return None
            mutator(project)
            cls.save_project(project)
            return project
    
    @classmethod
    def get_project(cls, project_id: str) -> Optional[Project]:
        """
        获取项目
        
        Args:
            project_id: 项目ID
            
        Returns:
            Project对象，如果不存在返回None
        """
        meta_path = cls._get_project_meta_path(project_id)
        data = read_json_or_none(meta_path, what=f"el proyecto {project_id}")
        if not isinstance(data, dict):
            return None          # no existe, se borró mientras se leía, o el archivo está ilegible (queda en el log)
        try:
            return Project.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(f"[estado] El proyecto {project_id} tiene un formato que no se entiende: {exc}")
            return None
    
    @classmethod
    def list_projects(cls, limit: int = 50) -> List[Project]:
        """
        列出所有项目
        
        Args:
            limit: 返回数量限制
            
        Returns:
            项目列表，按创建时间倒序
        """
        cls._ensure_projects_dir()
        
        projects = []
        for project_id in os.listdir(cls.PROJECTS_DIR):
            if not is_valid_storage_id(project_id, "proj_"):
                continue
            project = cls.get_project(project_id)
            if project:
                projects.append(project)
        
        # 按创建时间倒序排序
        projects.sort(key=lambda p: p.created_at, reverse=True)
        
        return projects[:limit]
    
    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """
        删除项目及其所有文件
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否删除成功
        """
        project_dir = cls._get_project_dir(project_id)
        
        if not os.path.exists(project_dir):
            return False
        
        shutil.rmtree(project_dir)
        with cls._locks_guard:
            cls._locks.pop(project_id, None)
        return True
    
    @classmethod
    def save_file_to_project(cls, project_id: str, file_storage, original_filename: str) -> Dict[str, str]:
        """
        保存上传的文件到项目目录
        
        Args:
            project_id: 项目ID
            file_storage: Flask的FileStorage对象
            original_filename: 原始文件名
            
        Returns:
            文件信息字典 {filename, path, size}
        """
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(files_dir, exist_ok=True)
        
        # 生成安全的文件名
        ext = os.path.splitext(original_filename)[1].lower()
        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(files_dir, safe_filename)
        
        # 保存文件
        file_storage.save(file_path)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        return {
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "path": file_path,
            "size": file_size
        }
    
    @classmethod
    def save_extracted_text(cls, project_id: str, text: str) -> None:
        """保存提取的文本"""
        atomic_write_text(cls._get_project_text_path(project_id), text, create_dir=False)
    
    @classmethod
    def get_extracted_text(cls, project_id: str) -> Optional[str]:
        """获取提取的文本"""
        text_path = cls._get_project_text_path(project_id)
        
        if not os.path.exists(text_path):
            return None
        
        with open(text_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    # Documento de la investigación en internet: un archivo más del material
    RESEARCH_DOCUMENT_FILENAME = 'investigacion-internet.md'

    @classmethod
    def _get_research_document_path(cls, project_id: str) -> str:
        return os.path.join(cls._get_project_files_dir(project_id), cls.RESEARCH_DOCUMENT_FILENAME)

    @classmethod
    def save_research_document(cls, project_id: str, markdown: str) -> Dict[str, Any]:
        """Guarda el Markdown de la investigación en files/ (sobrescribe el anterior)."""
        files_dir = cls._get_project_files_dir(project_id)
        if not os.path.isdir(cls._get_project_dir(project_id)):
            raise FileNotFoundError(f"El proyecto {project_id} ya no existe")
        os.makedirs(files_dir, exist_ok=True)
        path = cls._get_research_document_path(project_id)
        atomic_write_text(path, markdown)
        return {"path": path, "size": os.path.getsize(path)}

    @classmethod
    def delete_research_document(cls, project_id: str) -> bool:
        """Borra el documento de la investigación si existe. True si había uno."""
        try:
            os.remove(cls._get_research_document_path(project_id))
            return True
        except FileNotFoundError:
            return False

    @classmethod
    def get_research_document(cls, project_id: str) -> Optional[str]:
        """Markdown de la investigación, o None si el proyecto no la tiene."""
        path = cls._get_research_document_path(project_id)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    @classmethod
    def get_project_files(cls, project_id: str) -> List[str]:
        """获取项目的所有文件路径"""
        files_dir = cls._get_project_files_dir(project_id)
        
        if not os.path.exists(files_dir):
            return []
        
        return [
            os.path.join(files_dir, f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]
