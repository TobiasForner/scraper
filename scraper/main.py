import typer

from scraper.download.download import app as dl_typer
from scraper.files.files import app as files_typer
from scraper.adb.adb import app as adb_typer
from scraper.img.img import app as img_typer
from scraper.ebook.ebook import app as ebook_typer

app = typer.Typer()
app.add_typer(dl_typer, name="dl", help="Downloading files")
app.add_typer(files_typer, name="files", help="Manage local files")
app.add_typer(adb_typer, name="adb", help="Manage files on ADB device")
app.add_typer(img_typer, name="img", help="Manipulate local image files")
app.add_typer(
    ebook_typer, name="ebook", help="Assemble local text files into ebook formats"
)


if __name__ == "__main__":
    app()
