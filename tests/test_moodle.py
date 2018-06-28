import pytest
from unittest.mock import patch 
import sys
import os

sys.path.append(os.path.realpath('.'))

import moodle
from moodle.main import Parser
from moodle.main import Moodle


class TestGetSubjects:
    def setup(self):
        with open('tests/patterns/my.html') as fd:
            content = Parser(fd.read())

        with patch.object(Moodle, 'download', return_value=content):
            moodle = Moodle(None, 'http://example.org')
            self.subjects = list(moodle.get_subjects())

    def test_number_of_subjects(self):
        assert len(self.subjects) == 10

    def test_first_course(self):
        subject = self.subjects[0]

        assert len(subject) == 2
        assert subject[0] == 'Análisis Forense De Malware'
        assert subject[1] == 'https://campusvirtual.uclm.es/course/view.php?id=28723'


class TestGetSubjectContent:
    def setup(self):
        with open('tests/patterns/example1.html') as fd:
            content = Parser(fd.read())

        with patch.object(Moodle, 'download', return_value=content):
            moodle = Moodle(None, 'http://example.org')
            self.links = list(moodle.get_subject_content(None, 'whatever'))
        
    def test_link_number(self):
        assert len(self.links) == 29

    def test_links_values(self):
        assert self.links[0][0] == 'Avisos'
        assert self.links[1][0] == 'Introducción a la asignatura'
        assert self.links[2][0] == 'Introduccion y algoritmos clásicos'
        assert self.links[3][0] == 'Tarea sobre la sesión 1 de criptografía'
        assert self.links[4][0] == 'CriptoSimetrica-Flujo'
        assert self.links[5][0] == 'Cifrado en Bloque - DES'
        assert self.links[6][0] == 'Cifrado en bloque - AES'
        assert self.links[7][0] == 'Funciones Hash'
        assert self.links[8][0] == 'Manual DES'
        assert self.links[9][0] == 'Manual AES'
        assert self.links[10][0] == 'Manual modos cifrado'
        assert self.links[11][0] == 'Tarea sesión 2'
        assert self.links[12][0] == 'Cifrado RSA'
        assert self.links[13][0] == 'Ayuda aritmética modular'
        assert self.links[14][0] == 'Ayuda Teoría de Números'
        assert self.links[15][0] == 'Artículo sobre RSA'
        assert self.links[16][0] == 'Tarea sobre la sesión 3 de criptografía'
        assert self.links[17][0] == 'Software GenRSA'
        assert self.links[18][0] == 'Comentarios a la evaluación de la tarea del módulo 3'
        assert self.links[19][0] == 'Firma, Certificados y PKI'
        assert self.links[20][0] == 'Enunciado Ejercicio PKI'
        assert self.links[21][0] == 'Entrega ejercicio Módulo 4'
        assert self.links[22][0] == 'Bitcoin'
        assert self.links[23][0] == 'Red Tor'
        assert self.links[24][0] == 'Tarea sesión 5'
        assert self.links[25][0] == 'Esteganografía'
        assert self.links[26][0] == 'Enunciado Ejercicio'
        assert self.links[27][0] == 'NUEVA Imangen Mandril'
        assert self.links[28][0] == 'Entrega Ejercicio módulo 6'

