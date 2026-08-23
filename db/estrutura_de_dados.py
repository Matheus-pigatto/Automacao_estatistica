import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
import hashlib

@dataclass
class Sorteio:
    def __init__(self, dados: dict):
        self.concurso = dados.get('concurso')
        self.data = dados.get('data')
        self.numeros = dados.get('numeros', [])
        self.total = dados.get('total')

    def to_text(self):
        return f"[{self.concurso}] \n Números: {self.numeros}"