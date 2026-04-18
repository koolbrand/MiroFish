"""
本体生成服务
接口1：分析文本内容，生成适合社会模拟的实体和关系类型定义
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction

logger = logging.getLogger(__name__)


def _to_pascal_case(name: str) -> str:
    """将任意格式的名称转换为 PascalCase（如 'works_for' -> 'WorksFor', 'person' -> 'Person'）"""
    # 按非字母数字字符分割
    parts = re.split(r'[^a-zA-Z0-9]+', name)
    # 再按 camelCase 边界分割（如 'camelCase' -> ['camel', 'Case']）
    words = []
    for part in parts:
        words.extend(re.sub(r'([a-z])([A-Z])', r'\1_\2', part).split('_'))
    # 每个词首字母大写，过滤空串
    result = ''.join(word.capitalize() for word in words if word)
    return result if result else 'Unknown'


# 本体生成的系统提示词
ONTOLOGY_SYSTEM_PROMPT = """Eres un experto profesional en diseño de ontologías de grafos de conocimiento. Tu tarea es analizar el contenido textual y los requisitos de simulación dados, y diseñar los tipos de entidad y los tipos de relación adecuados para una **simulación de opinión pública en redes sociales**.

**Importante: debes producir datos en formato JSON válido; no generes ningún otro contenido.**

## Contexto de la tarea principal

Estamos construyendo un **sistema de simulación de opinión pública en redes sociales**. En este sistema:
- Cada entidad es una "cuenta" o "sujeto" que puede expresarse, interactuar y propagar información en redes sociales
- Las entidades se influyen mutuamente, se retuitean, se comentan y se responden entre sí
- Necesitamos simular las reacciones de todas las partes y las rutas de propagación de la información en un evento de opinión pública

Por tanto, **las entidades deben ser sujetos reales que existen y pueden expresarse e interactuar en redes sociales**:

**Pueden ser**:
- Personas concretas (figuras públicas, protagonistas, líderes de opinión, expertos académicos, personas comunes)
- Empresas, compañías (incluidas sus cuentas oficiales)
- Organizaciones (universidades, asociaciones, ONG, sindicatos, etc.)
- Dependencias gubernamentales, entes reguladores
- Medios de comunicación (periódicos, canales de TV, medios independientes, sitios web)
- Las propias plataformas de redes sociales
- Representantes de grupos específicos (por ejemplo, asociaciones de exalumnos, fandoms, grupos de defensa de derechos)

**No pueden ser**:
- Conceptos abstractos (como "opinión pública", "emoción", "tendencia")
- Temas/asuntos (como "integridad académica", "reforma educativa")
- Puntos de vista/actitudes (como "partidarios", "opositores")

## Formato de salida

Por favor produce JSON con la siguiente estructura:

```json
{
    "entity_types": [
        {
            "name": "Nombre del tipo de entidad (en inglés, PascalCase)",
            "description": "Descripción breve (en inglés, máximo 100 caracteres)",
            "attributes": [
                {
                    "name": "Nombre del atributo (en inglés, snake_case)",
                    "type": "text",
                    "description": "Descripción del atributo"
                }
            ],
            "examples": ["Entidad de ejemplo 1", "Entidad de ejemplo 2"]
        }
    ],
    "edge_types": [
        {
            "name": "Nombre del tipo de relación (en inglés, UPPER_SNAKE_CASE)",
            "description": "Descripción breve (en inglés, máximo 100 caracteres)",
            "source_targets": [
                {"source": "Tipo de entidad origen", "target": "Tipo de entidad destino"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "Breve análisis del contenido del texto"
}
```

## Guía de diseño (extremadamente importante)

### 1. Diseño de tipos de entidad — debes cumplir estrictamente

**Requisito de cantidad: debe haber exactamente 10 tipos de entidad**

**Requisito de jerarquía (deben incluirse tanto tipos específicos como tipos de respaldo)**:

Tus 10 tipos de entidad deben contener la siguiente jerarquía:

A. **Tipos de respaldo (obligatorios, colocados como los 2 últimos de la lista)**:
   - `Person`: tipo de respaldo para cualquier persona física. Cuando una persona no encaje en tipos más específicos, se asigna a este.
   - `Organization`: tipo de respaldo para cualquier organización. Cuando una organización no encaje en tipos más específicos, se asigna a este.

B. **Tipos específicos (8, diseñados en función del contenido del texto)**:
   - Diseña tipos más específicos para los roles principales que aparecen en el texto
   - Por ejemplo: si el texto trata sobre un caso académico, puedes tener `Student`, `Professor`, `University`
   - Por ejemplo: si el texto trata sobre un caso empresarial, puedes tener `Company`, `CEO`, `Employee`

**Por qué se necesitan los tipos de respaldo**:
- En el texto pueden aparecer personas diversas, como "profesor de secundaria", "un transeúnte", "un internauta"
- Si no hay un tipo específico que encaje, deben clasificarse como `Person`
- De la misma manera, organizaciones pequeñas o grupos temporales deben clasificarse como `Organization`

**Principios de diseño para los tipos específicos**:
- Identifica en el texto los roles clave o más frecuentes
- Cada tipo específico debe tener límites claros, evitando solapamientos
- La description debe explicar claramente la diferencia entre este tipo y el de respaldo

### 2. Diseño de tipos de relación

- Cantidad: 6-10
- Las relaciones deben reflejar vínculos reales en la interacción en redes sociales
- Asegúrate de que source_targets cubra los tipos de entidad que hayas definido

### 3. Diseño de atributos

- 1-3 atributos clave por tipo de entidad
- **Atención**: los nombres de atributo no pueden ser `name`, `uuid`, `group_id`, `created_at`, `summary` (palabras reservadas del sistema)
- Recomendados: `full_name`, `title`, `role`, `position`, `location`, `description`, etc.

## Referencia de tipos de entidad

**Personas (específicos)**:
- Student: estudiante
- Professor: profesor/académico
- Journalist: periodista
- Celebrity: celebridad/influencer
- Executive: ejecutivo
- Official: funcionario público
- Lawyer: abogado
- Doctor: médico

**Personas (respaldo)**:
- Person: cualquier persona física (cuando no encaja en los tipos específicos anteriores)

**Organizaciones (específicos)**:
- University: institución de educación superior
- Company: empresa/compañía
- GovernmentAgency: organismo gubernamental
- MediaOutlet: medio de comunicación
- Hospital: hospital
- School: escuela primaria/secundaria
- NGO: organización no gubernamental

**Organizaciones (respaldo)**:
- Organization: cualquier organización (cuando no encaja en los tipos específicos anteriores)

## Referencia de tipos de relación

- WORKS_FOR: trabaja en
- STUDIES_AT: estudia en
- AFFILIATED_WITH: afiliado a
- REPRESENTS: representa a
- REGULATES: regula a
- REPORTS_ON: informa sobre
- COMMENTS_ON: comenta sobre
- RESPONDS_TO: responde a
- SUPPORTS: apoya a
- OPPOSES: se opone a
- COLLABORATES_WITH: colabora con
- COMPETES_WITH: compite con
"""


class OntologyGenerator:
    """
    本体生成器
    分析文本内容，生成实体和关系类型定义
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成本体定义
        
        Args:
            document_texts: 文档文本列表
            simulation_requirement: 模拟需求描述
            additional_context: 额外上下文
            
        Returns:
            本体定义（entity_types, edge_types等）
        """
        # 构建用户消息
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        lang_instruction = get_language_instruction()
        system_prompt = (
            f"{lang_instruction}\n"
            "CRITICAL: The `description` fields and `analysis_summary` field MUST be written in the language specified above. "
            "Do NOT output Chinese for those fields unless that is the target language.\n"
            "IMPORTANT: Entity type names MUST be in English PascalCase (e.g., 'PersonEntity', 'MediaOrganization'). "
            "Relationship type names MUST be in English UPPER_SNAKE_CASE (e.g., 'WORKS_FOR'). "
            "Attribute names MUST be in English snake_case.\n\n"
            f"{ONTOLOGY_SYSTEM_PROMPT}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # 调用LLM
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        # 验证和后处理
        result = self._validate_and_process(result)
        
        return result
    
    # 传给 LLM 的文本最大长度（5万字）
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """构建用户消息"""
        
        # 合并文本
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # 如果文本超过5万字，截断（仅影响传给LLM的内容，不影响图谱构建）
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(el original tiene {original_length} caracteres; se tomaron los primeros {self.MAX_TEXT_LENGTH_FOR_LLM} para el análisis ontológico)..."

        message = f"""## Requisitos de simulación

{simulation_requirement}

## Contenido del documento

{combined_text}
"""

        if additional_context:
            message += f"""
## Información adicional

{additional_context}
"""

        message += """
Por favor, a partir del contenido anterior, diseña los tipos de entidad y los tipos de relación adecuados para la simulación de opinión pública social.

**Reglas de obligado cumplimiento**:
1. Debes producir exactamente 10 tipos de entidad
2. Los 2 últimos deben ser los tipos de respaldo: Person (respaldo de personas) y Organization (respaldo de organizaciones)
3. Los 8 primeros son tipos específicos diseñados en función del contenido del texto
4. Todos los tipos de entidad deben ser sujetos reales capaces de expresarse; no pueden ser conceptos abstractos
5. Los nombres de atributo no pueden ser palabras reservadas como name, uuid, group_id; usa en su lugar full_name, org_name, etc.
"""

        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证和后处理结果"""
        
        # 确保必要字段存在
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        # 验证实体类型
        # 记录原始名称到 PascalCase 的映射，用于后续修正 edge 的 source_targets 引用
        entity_name_map = {}
        for entity in result["entity_types"]:
            # 强制将 entity name 转为 PascalCase（Zep API 要求）
            if "name" in entity:
                original_name = entity["name"]
                entity["name"] = _to_pascal_case(original_name)
                if entity["name"] != original_name:
                    logger.warning(f"Entity type name '{original_name}' auto-converted to '{entity['name']}'")
                entity_name_map[original_name] = entity["name"]
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # 确保description不超过100字符
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # 验证关系类型
        for edge in result["edge_types"]:
            # 强制将 edge name 转为 SCREAMING_SNAKE_CASE（Zep API 要求）
            if "name" in edge:
                original_name = edge["name"]
                edge["name"] = original_name.upper()
                if edge["name"] != original_name:
                    logger.warning(f"Edge type name '{original_name}' auto-converted to '{edge['name']}'")
            # 修正 source_targets 中的实体名称引用，与转换后的 PascalCase 保持一致
            for st in edge.get("source_targets", []):
                if st.get("source") in entity_name_map:
                    st["source"] = entity_name_map[st["source"]]
                if st.get("target") in entity_name_map:
                    st["target"] = entity_name_map[st["target"]]
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API 限制：最多 10 个自定义实体类型，最多 10 个自定义边类型
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # 去重：按 name 去重，保留首次出现的
        seen_names = set()
        deduped = []
        for entity in result["entity_types"]:
            name = entity.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                deduped.append(entity)
            elif name in seen_names:
                logger.warning(f"Duplicate entity type '{name}' removed during validation")
        result["entity_types"] = deduped

        # 兜底类型定义
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # 检查是否已有兜底类型
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # 需要添加的兜底类型
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # 如果添加后会超过 10 个，需要移除一些现有类型
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 计算需要移除多少个
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # 从末尾移除（保留前面更重要的具体类型）
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # 添加兜底类型
            result["entity_types"].extend(fallbacks_to_add)
        
        # 最终确保不超过限制（防御性编程）
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        将本体定义转换为Python代码（类似ontology.py）
        
        Args:
            ontology: 本体定义
            
        Returns:
            Python代码字符串
        """
        code_lines = [
            '"""',
            '自定义实体类型定义',
            '由MiroFish自动生成，用于社会舆论模拟',
            '"""',
            '',
            'from pydantic import Field, BaseModel',
            'from typing import Optional',
            '',
            '# Graphiti extracts ontology automatically; these classes are for documentation only.',
            'EntityText = Optional[str]',
            '',
            'class EntityModel(BaseModel):',
            '    pass',
            '',
            'class EdgeModel(BaseModel):',
            '    pass',
            '',
            '',
            '# ============== 实体类型定义 ==============',
            '',
        ]
        
        # 生成实体类型
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== 关系类型定义 ==============')
        code_lines.append('')
        
        # 生成关系类型
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # 转换为PascalCase类名
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # 生成类型字典
        code_lines.append('# ============== 类型配置 ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # 生成边的source_targets映射
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)

