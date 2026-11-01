from setuptools import find_packages, setup

package_name = "robotica_bimanual"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/celda.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    description="Nodos ROS 2 de la celda bimanual: puente EGM, detección de la caja y coordinador.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "nodo_puente = robotica_bimanual.nodo_puente:main",
            "nodo_caja = robotica_bimanual.nodo_caja:main",
            "nodo_coordinador = robotica_bimanual.nodo_coordinador:main",
        ],
    },
)
