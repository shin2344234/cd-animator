cmake_minimum_required(VERSION 3.20)
project(CDAnimator LANGUAGES CXX)

# CD Animator Loader: an ASI plugin for Crimson Desert that hands the game
# every file in the CDAnimator folder beside it in place of the game's file
# of that name, so a clip made in CD Animator can be played without a pack.
# The file it produces is CDAnimator.asi.

if(NOT WIN32)
    message(FATAL_ERROR "The loader targets Windows only.")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>") # static CRT, no redist needed
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include(FetchContent)
set(FETCHCONTENT_QUIET FALSE)

# MinHook is here only for its HDE64 length decoder, which farhook uses to
# measure the bytes it steals. No MinHook hook is ever created.
FetchContent_Declare(
    minhook
    GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
    GIT_TAG        master
)
FetchContent_MakeAvailable(minhook)

add_library(CDAnimator SHARED
    src/dllmain.cpp
    src/core/loader.cpp
    src/core/log.cpp
    src/core/paths.cpp
    src/game/mem.cpp
    src/game/farhook.cpp
    src/game/files.cpp
    src/game/states.cpp
)

target_include_directories(CDAnimator PRIVATE src ${minhook_SOURCE_DIR}/src/hde)
target_link_libraries(CDAnimator PRIVATE minhook)
target_compile_definitions(CDAnimator PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX _CRT_SECURE_NO_WARNINGS)
target_compile_options(CDAnimator PRIVATE /utf-8 /W3)

set_target_properties(CDAnimator PROPERTIES PREFIX "" SUFFIX ".asi" OUTPUT_NAME "CDAnimator")

if(MSVC)
    target_compile_options(CDAnimator PRIVATE /guard:cf)
    target_link_options(CDAnimator PRIVATE /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /guard:cf)
endif()

# The release zip: the plugin and MinHook's notice, which its BSD licence
# asks to ship with the binary, flat like the other mods' manual zips.
file(STRINGS "${CMAKE_SOURCE_DIR}/src/version.h" CDA_VERSION_LINE REGEX "#define CDA_VERSION ")
string(REGEX MATCH "[0-9]+\\.[0-9]+\\.[0-9]+" CDA_VERSION "${CDA_VERSION_LINE}")
set(CDA_ZIP "CDAnimator-Loader-${CDA_VERSION}.zip")

add_custom_command(TARGET CDAnimator POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_SOURCE_DIR}/dist"
    COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_FILE:CDAnimator>" "${CMAKE_SOURCE_DIR}/dist/"
    COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_SOURCE_DIR}/MinHook-LICENSE.txt" "${CMAKE_SOURCE_DIR}/dist/"
    COMMAND ${CMAKE_COMMAND} -E rm -f "${CDA_ZIP}"
    COMMAND ${CMAKE_COMMAND} -E tar cf "${CDA_ZIP}" --format=zip CDAnimator.asi MinHook-LICENSE.txt
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/dist"
    COMMENT "Staging dist/ and ${CDA_ZIP}"
    VERBATIM
)
