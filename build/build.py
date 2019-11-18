"""Build script for local and azure pipeline builds."""

import os, sys
import time
import timeit
import subprocess
import shutil
import argparse
import warnings
import tempfile
import fnmatch
from pathlib import Path
from tempfile import gettempdir

VERBOSE = True

def main():
    """The main entry point."""
    script_args = parse_args()
    # Set the global vars for the script
    global VERBOSE
    build = create_build_runner(script_args)
    build.run()

def parse_args():
    parser = argparse.ArgumentParser(description='Builds the DeliveryOptimization cross-platform client.')
    parser.add_argument(
        '--operation', dest='operation', type=str,
        help='The operation to perform. e.g. generate/build/cleanonly. Default is generate+build.'
    )
    parser.add_argument(
        '--platform', dest='platform', type=str,
        help='The target platform. e.g. windows or linux.'
    )
    parser.add_argument(
        '--arch', dest='arch', type=str,
        help='The target architecture. e.g x86, x64, or arm.'
    )
    parser.add_argument(
        '--config', dest='config', type=str,
        help='The target configuration. e.g. debug or release.'
    )
    parser.add_argument(
        '--compiler', dest='compiler', type=str,
        help='The compiler to use. e.g. gnu, or msvc.'
    )
    parser.add_argument(
        '--cmaketarget', dest='cmaketarget', type=str,
        help='The cmake target to build. e.g. dosvc or dosvc_unity'
    )
    parser.add_argument(
        '--vcpkgdir', dest='vcpkgdir', type=str,
        help='The path to use for building (cmake cache, obj files, bin files, etc.).'
    )
    parser.add_argument(
        '--clean', dest='clean', action='store_true',
        help='Remove built binaries before re-building them.'
    )
    parser.add_argument(
        '--runtests', dest='runtests', action='store_true',
        help='Runs all unit test executables in default executable location.'
    )
    parser.add_argument(
        '--as-service', dest='as_service', action='store_true',
        help='Builds the client for running as a daemon'
    )

    return parser.parse_args()

class NotSupportedTargetPlatformError(ValueError):
    pass

class NotSupportedHostEnvironmentError(ValueError):
    pass

def create_build_runner(script_args):
    """Creates the appropriate subclass of BuildRunnerBase.

    Chooses the correct BuildRunner class for the target platform.
    Args:
        script_args (namespace):
            The arguments passed to the script parsed by argparse.

    Returns:
        The appropriate subclass of Build.
    """

    # Default cases where platform was not specified
    if script_args.platform is None and is_running_on_windows():
        return WindowsBuildRunner(script_args)
    elif script_args.platform is None and is_running_on_linux():
        return LinuxBuildRunner(script_args)
    elif script_args.platform is None and is_running_on_osx():
        return OsxBuildRunner(script_args)
    elif script_args.platform is None:
        raise ValueError('Target platform was not specified and could not be deduced from the current host environment.')
    # Cases where platform was specified in script args.
    elif script_args.platform.lower() == 'windows':
        if is_running_on_windows():
            return WindowsBuildRunner(script_args)
        else:
            raise NotSupportedHostEnvironmentError('Building for Windows on this host environment is not supported.')
    elif script_args.platform.lower() == 'linux':
        if is_running_on_linux():
            return LinuxBuildRunner(script_args)
        else:
            raise NotSupportedHostEnvironmentError('Building for Linux on this host environment is not supported.')
    elif script_args.platform.lower() == 'osx':
        if is_running_on_osx():
            return LinuxBuildRunner(script_args)
        else:
            raise NotSupportedHostEnvironmentError('Building for OsX on this host environment is not supported.')
    else:
        raise NotSupportedTargetPlatformError(f'Currently builds for {script_args.platform.lower()} are not supported.')

#region BuildRunner classes

class BuildRunnerBase(object):
    """Base class for specific platform builds.

    BuildRunner classes will inherit from this class
    and will implement/override/add additional functionality
    for that specific build.

    Args:
        script_args (namespace):
            The arguments passed to the script parsed by argparse.
    """

    def __init__(self, script_args):
        super().__init__()
        self.timeToClean = 0
        self.timeToGenerate = 0
        self.timeToBuild = 0

        self.operation_type = script_args.operation
        self.project_root_path = get_project_root_path()
        self.vcpkg_root_path = get_env_var('BUILD_VCPKGDIR') if script_args.vcpkgdir is None else script_args.vcpkgdir
        self.cmake_target = None
        if (script_args.cmaketarget is None):
            if (script_args.runtests != True):
                self.cmake_target = "all"
        else:
            self.cmake_target = script_args.cmaketarget
        self.script_args = script_args
        self.is_clean_build = self.script_args.clean
        self.run_tests = self.script_args.runtests
        if self.script_args.arch:
            self.arch = self.script_args.arch.lower()
        elif get_env_var('BUILD_ARCHITECTURE'):
            self.arch = get_env_var('BUILD_ARCHITECTURE')
        else:
            self.arch = 'x64'

        if not (self.arch == 'x64' or self.arch == 'x86'
            or self.arch == 'arm'):
            raise ValueError(f'Building {self.arch} architecture for {self.platform} is not supported.')

        if self.script_args.config:
            self.config = self.script_args.config.lower()
        elif get_env_var('BUILD_CONFIGURATION'):
            self.config = get_env_var('BUILD_CONFIGURATION').lower()
        else:
            self.config = 'debug'

        if not (self.config == 'debug' or self.config == 'release'):
            raise ValueError(f'Building {self.config} configuration for {self.platform} is not supported.')

        self.as_service = script_args.as_service

        self.source_path = get_project_root_path()

    @property
    def flavor(self):
        """The unique flavor string for this build.

        Returns:
            The unique flavor string for this build.
            e.g. win-x64-msvc-debug, linux-arm-clang-release
        """
        return f'{self.platform}-{self.arch}-{self.compiler}-{self.config}'

    @property
    def platform(self):
        """The target platform.

        Should be overriden by subclass.

        Returns:
            The target platform string.
            e.g. windows, linux
        """
        pass

    @property
    def compiler(self):
        """The compiler to use.

        Should be overriden by subclass.

        Returns:
            The name of the compiler.
            e.g. clang, gnu, msvc
        """
        pass

    @property
    def generator(self):
        """The CMake generator for this build.

        Can be overriden by subclass.
        Tells CMake what type of build to generate.
        'Unix Makefiles' will generate a set of make files,
        'Visual Studio ...' will generate vs proj files,
        etc.

        Returns:
            CMake generator ID as string.
            None if default generator should be used (not recommended).
        """
        return None

    @property
    def build_path(self):
        """Path for the build."""
        return get_default_build_path(self.flavor)

    def run(self):
        if self.cmake_target != None:
            """Executes the Build."""
            self.print_start_build_msg()

            if self.is_clean_build:
                self.clean()

            if self.operation_type:
                if self.operation_type.lower() == "generate":
                    self.generate()
                elif self.operation_type.lower() == "build":
                    self.build()
                elif self.operation_type.lower() == "cleanonly":
                    if not self.is_clean_build:
                        self.clean()
                else:
                    raise ValueError(f'Invalid operation specified: {self.operation_type}')
            else:
                self.generate()
                self.build()

            self.print_end_build_msg()
            self.print_times()

        if self.run_tests:
            self.tests()

    def print_start_build_msg(self):
        """Prints a message at the start of Build.run.

        Can be overriden by subclass.
        Typically subclasses will call
        super().print_start_build_msg before adding their own
        print statements.
        """
        print('Starting Build')
        print(f'Target OS: {self.platform.capitalize()}')
        print(f'Flavor: {self.flavor}')
        print(f'Arch: {self.arch}')
        print(f'Config: {self.config}')
        print(f'CMake Target: {self.cmake_target}')
        print(f'CMake Generator: {self.generator}')
        print(f'Compiler: {self.compiler}')
        print(f'Clean: {self.is_clean_build}')
        print(f'Source Path: {self.source_path}')
        print(f'Build Path: {self.build_path}')

    def print_end_build_msg(self):
        """Prints a message at the end of Build.run."""
        print('Build Complete')

    def print_times(self):
        print(f'Time to clean: {self.timeToClean}')
        print(f'Time to generate: {self.timeToGenerate}')
        print(f'Time to build: {self.timeToBuild}')

    def clean(self):
        """Deletes the output directory(s) for this Build."""
        build_path = self.build_path
        print(f'Purging: {build_path}')
        start_time = timeit.default_timer()
        if os.path.exists(build_path):
            shutil.rmtree(build_path)
        self.timeToClean = timeit.default_timer() - start_time

    def generate(self):
        """Executes the generate phase of the build."""

        if self.vcpkg_root_path is None:
            raise ValueError('vcpkg root directory was not specified')

        # Only Windows versions of cmake have
        # -S <source dir> or -B <build dir> options.
        # To support cmake on all platforms,
        # we need to create and change to our build output dir.
        original_dir = os.getcwd()
        os.makedirs(self.build_path, exist_ok=True)
        os.chdir(self.build_path)
        generate_command = self.create_generate_command()
        start_time = timeit.default_timer()
        run_command(generate_command)
        self.timeToGenerate = timeit.default_timer() - start_time
        os.chdir(original_dir)

    def create_generate_command(self):
        """Creates the command to use in the generate phase.

        Subclasses can override this method,
        but most likely subclasses will want to
        override generate_options instead.

        Returns:
            The generate command as a list of strings.
        """
        return ['cmake', self.source_path] + self.generate_options

    @property
    def generate_options(self):
        """Additional options to use in generate.

        Can be overriden by subclass.
        Typically subclasses will call
        super().generate_options + ['--foo', 'My option value']
        to add their own options to the generate_command list.

        Returns:
            The list of additional generate options.
        """
        generate_options = []
        if self.generator:
            generate_options.extend(['-G', self.generator])

        if self.config.lower() == "debug":
            generate_options.extend(["-DCMAKE_BUILD_TYPE=Debug"])
        else:
            generate_options.extend(["-DCMAKE_BUILD_TYPE=Release"])

        if self.as_service:
            generate_options.extend(["-DDO_BUILD_AS_SERVICE=ON"])

        return generate_options

    def build(self):
        """Executes the build phase of the build."""
        build_command = self.create_build_command()
        print('Executing: {}'.format(' '.join(build_command)))
        start_time = timeit.default_timer()
        run_command(build_command)
        self.timeToBuild = timeit.default_timer() - start_time

    def create_build_command(self):
        """Creates the command to use in the build phase.

        Subclasses can override this method,
        but most likely subclasses will want to
        override build_options instead.

        Returns:
            The build command as a list of strings.
        """
        return ['cmake', '--build', self.build_path] + self.build_options

    @property
    def build_options(self):
        """Additional options to use in build.

        Can be overriden by subclass.
        Typically subclasses will call
        super().build_options + ['--foo', 'My option value'].

        Returns:
            The list of additional build options.
        """
        return ["--target", self.cmake_target]

    def tests(self):
        directory = os.path.join(gettempdir(), self.build_path, "test")
        if is_running_on_windows():
            test_exe_name = os.path.join(directory, "docs_tests.exe")
        elif is_running_on_linux():
            test_exe_name = os.path.join(directory, "docs_tests")
        elif build.is_running_on_osx():
            test_exe_name = os.path.join(directory, "docs_tests") #TBD

        subprocess.call([test_exe_name])

class WindowsBuildRunner(BuildRunnerBase):
    """Windows BuildRunner class."""

    def __init__(self, script_args):
        super().__init__(script_args)
        if (script_args.compiler is not None
            and script_args.compiler.lower() != self.compiler):
            raise ValueError('Only msvc compiler is supported for building on Windows.')

        if self.arch.startswith('arm'):
            warn_message = """
    Uh Oh! Windows arm builds are broken right now. Expect to hit errors when running arm flavors of the build."""
            warnings.warn(warn_message)

    @property
    def platform(self):
        return 'windows'

    @property
    def compiler(self):
        return 'msvc'

    @property
    def generator(self):
        if (self.arch == 'x64'):
            return 'Visual Studio 15 2017 Win64'
        else:
            return 'Visual Studio 15 2017'

    @property
    def generate_options(self):
        return super().generate_options + [
                f'-DCMAKE_TOOLCHAIN_FILE={get_vcpkg_toolchain_file_path(self.vcpkg_root_path)}',
                f'-DVCPKG_TARGET_TRIPLET={self._vcpkg_triplet}'
            ]

    @property
    def build_options(self):
        return super().build_options + ['--config', self.config]

    @property
    def _vcpkg_triplet(self):
        """The triplet string required by vcpkg."""
        # There is no static version of the arm or arm64 packages.
        # if self.arch.startswith('arm'):
        #     return f'{self.arch}-{self.platform}'
        # else:
        #     return f'{self.arch}-{self.platform}-static'

        # We don't use the 'static' vcpkg install yet.
        # Looks like vcpkg uses static libs by default.
        return f'{self.arch}-{self.platform}'

class LinuxBuildRunner(BuildRunnerBase):
    """Linux BuildRunner class."""

    def __init__(self, script_args):
        super().__init__(script_args)
        if self.script_args.compiler:
            self._compiler = self.script_args.compiler.lower()
        elif get_env_var('BUILD_COMPILER'):
            self._compiler = get_env_var('BUILD_COMPILER').lower()
        else:
            self._compiler = 'gnu'

        if not (self.compiler == 'gnu' or self.compiler == 'clang'):
            raise ValueError('Only gnu and clang compilers are supported for building on Linux.')

    @property
    def platform(self):
        return 'linux'

    @property
    def compiler(self):
        return self._compiler

    @property
    def generator(self):
        return 'Unix Makefiles'

    @property
    def generate_options(self):
        toolchain_file_path = get_cmake_toolchain_file_path(
            self.platform,
            self.arch,
            self.compiler,
            self.project_root_path
        )
        generate_options = super().generate_options + [
            f'-DCMAKE_TOOLCHAIN_FILE={get_vcpkg_toolchain_file_path(self.vcpkg_root_path)}',
            f'-DVCPKG_CHAINLOAD_TOOLCHAIN_FILE={toolchain_file_path}'
        ]

        if self.arch.startswith('arm'):
            zlib_dir = get_env_var('ZLIB_ROOT_DIR')
            if zlib_dir is not None:
                generate_options.append(f'-DZLIB_ROOT={zlib_dir}')

        return generate_options

class OsxBuildRunner(BuildRunnerBase):
    """OsX BuildRunner class."""

    def __init__(self, script_args):
        super().__init__(script_args)
        if self.script_args.compiler:
            self._compiler = self.script_args.compiler.lower()
        elif get_env_var('BUILD_COMPILER'):
            self._compiler = get_env_var('BUILD_COMPILER').lower()
        else:
            self._compiler = 'gnu'

        if not (self.compiler == 'gnu' or self.compiler == 'clang'):
            raise ValueError('Only gnu and clang compilers are supported for building on OsX.')

    @property
    def platform(self):
        return 'osx'

    @property
    def compiler(self):
        return self._compiler

    @property
    def generator(self):
        return 'Unix Makefiles'

    @property
    def generate_options(self):
        toolchain_file_path = get_cmake_toolchain_file_path(
            self.platform,
            self.arch,
            self.compiler,
            self.project_root_path
        )
        generate_options = super().generate_options + [
            f'-DCMAKE_TOOLCHAIN_FILE={get_vcpkg_toolchain_file_path(self.vcpkg_root_path)}',
            f'-DVCPKG_CHAINLOAD_TOOLCHAIN_FILE={toolchain_file_path}'
        ]

        if self.arch.startswith('arm'):
            zlib_dir = get_env_var('ZLIB_ROOT_DIR')
            if zlib_dir is not None:
                generate_options.append(f'-DZLIB_ROOT={zlib_dir}')

        return generate_options

#endrgion

#region Util Functions

def get_os_name():
    """Gets the friendly OS name.

    This value can differ for local builds vs pipeline builds.

    Returns:
        The friendly version of the OS Name.
    """
    if get_env_var('AGENT_OS'):
        return get_env_var('AGENT_OS').lower()
    else:
        return sys.platform.lower()

def is_running_on_windows():
    """Indicates if this build is running on a Windows agent/machine

    Returns:
        True if the build is running on a Windows agent/machine.
        False otherwise.
    """
    return get_os_name().startswith('win')

def is_running_on_linux():
    """Indicates if this build is running on a Linux agent/machine

    Returns:
        True if the build is running on a Linux agent/machine.
        False otherwise.
    """
    return get_os_name().startswith('linux')

def is_running_on_osx():
    """Indicates if this build is running on a OsX agent/machine

    Returns:
        True if the build is running on a Osx agent/machine.
        False otherwise.
    """
    return get_os_name().startswith('darwin')

def get_project_root_path():
    """Gets the root path to our git repo.

    Note that this function may return a different value
    than what is expected after calling os.chdir.

    Returns:
        The root path to our git repo.
    """
    script_path = os.path.dirname(os.path.realpath(__file__))
    print(f'script_path={script_path}')
    return os.path.abspath(os.path.join(script_path, '..'))

def get_cmake_files_path(root_path=None):
    """Gets the path to custom cmake 'include' files for our bulid

    Args:
        root_path (str):
            The project root path.
            If None, uses get_project_root_path() instead.

    Returns:
        The path to our custom cmake 'include' files.
    """
    if root_path is None:
        root_path = get_project_root_path()
    return os.path.abspath(os.path.join(root_path, 'build', 'cmake'))

def get_cmake_toolchain_file_name(platform, arch, compiler):
    """Gets the cmake toolchain file name for the given params.

    Args:
        platform (str):
            The target platform for the build.
            e.g. windows or linux.
        arch (str):
            The target processor architecture for the build.
            e.g. x64 or arm
        compiler (str):
            The compiler toolset to use for the build.
            e.g. msvc, gnu, clang

    Returns:
        The cmake toolchain file name for the given params.
    """
    return f'toolchain-{platform}-{arch}-{compiler}.cmake'

def get_cmake_toolchain_file_path(platform, arch, compiler, root_path=None):
    """Gets the full path to the cmake toolchain file for the given parms.

    Args:
        platform (str):
            The target platform for the build.
            e.g. windows or linux.
        arch (str):
            The target processor architecture for the build.
            e.g. x64 or arm
        compiler (str):
            The compiler toolset to use for the build.
            e.g. msvc, gnu, clang
        root_path (str):
            The project root path.
            If None, uses get_project_root_path() instead.

    Returns:
        The full path to the cmake toolchain file for the given parms.
    """
    if root_path is None:
        root_path = get_project_root_path()
    return os.path.join(
        get_cmake_files_path(root_path),
        get_cmake_toolchain_file_name(platform, arch, compiler)
    )

def get_vcpkg_toolchain_file_path(root_path):
    """Gets the path to the vcpkg cmake toolchain file.

    Args:
        root_path (str):
            The vcpkg root path.

    Returns:
        The path to the vcpkg cmake toolchain file.
    """
    return os.path.abspath(os.path.join(root_path, 'scripts', 'buildsystems', 'vcpkg.cmake'))


def get_default_build_path(flavor=None):
    """Gets the default path to the build folder.

    Uses the 'flavor' property to construct the path if available.

    Args:
        flavor (str):
            The unique flavor string for the build.

    Returns:
        The default bin path.
    """
    build_path = os.path.join(tempfile.gettempdir(), "build_do_proxywrapper", flavor)
    return build_path

def get_env_var(name):
    """Gets the environment variable value or None.

    Utility function to get an environment variable value
    given the name of the environment variable.
    Returns None if the environment variable is not set/present.

    Args:
        name (str):
            The name of the environment variable.

    Returns:
        The value of the environment variable with name.
        None if the environment variable is not set/present.
    """
    if name.upper() in os.environ:
        return os.environ[name.upper()]
    else:
        return None

def run_command(command):
    """Runs the given command.

    Args:
        command (list):
            The command to run in list form.

    Raises:
        subprocess.CalledProcessError
    """
    command_string = ' '.join(command)
    try:
        print(f'Running command {command_string}.')
        _check_call(command)
    except subprocess.CalledProcessError:
        print(f'Running {command_string} failed. Rethrowing exception')
        raise

def _check_call(command):
    """Wrapper around subprocess.check_call.

    Handles piping output in various cases:
    - Verbose logging turned on/off.

    Args:
        command (list):
            The command to run in list form.

    Raises:
        subprocess.CalledProcessError
    """
    # We pipe stderr to stdout because
    # some commands (like apt) write output to stderr,
    # but that output should not cause a failure
    # in the pipeline build job.
    global VERBOSE
    if VERBOSE:
        subprocess.check_call(
            command,
            stderr=subprocess.STDOUT
        )
    else:
        subprocess.check_call(
            command,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL
        )

#endregion

if __name__ == "__main__":
    main()
