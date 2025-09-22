#!/bin/bash

# =============================================================================
# Script di Build Docker per MIRCrew Smart Indexer
# Builda l'immagine e la rende disponibile localmente per Portainer
# =============================================================================

set -e  # Exit on error

# Configurazione
IMAGE_NAME="mircrew-smart-indexer"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funzioni di utilità
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Funzione per controllare se Docker è in esecuzione
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker non è in esecuzione o non accessibile"
        exit 1
    fi
    log_info "Docker è attivo e accessibile"
}

# Funzione per controllare se i file e le directory necessarie esistono
check_files() {
    local required_files=("Dockerfile" "app.py")
    local required_dirs=("config" "indexer" "models" "services" "utils")
    
    # Controlla file principali
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "File richiesto non trovato: $file"
            exit 1
        fi
    done
    
    # Controlla directory principali
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_error "Directory richiesta non trovata: $dir"
            exit 1
        fi
    done
    
    log_info "Tutti i file e directory richiesti sono presenti"
}

# Funzione per fare build dell'immagine Docker
build_image() {
    log_info "Avvio build dell'immagine Docker: $FULL_IMAGE_NAME"
    
    # Mostra immagine esistente se presente
    if docker images -q "$FULL_IMAGE_NAME" >/dev/null 2>&1; then
        log_warning "Immagine esistente trovata: $FULL_IMAGE_NAME"
        echo "Verrà sostituita con la nuova build..."
    fi
    
    # Build nuova immagine
    docker build -t "$FULL_IMAGE_NAME" . || {
        log_error "Build dell'immagine fallita"
        exit 1
    }
    
    log_success "Build dell'immagine completata: $FULL_IMAGE_NAME"
}

# Funzione per salvare l'immagine in un file tar (per trasferimento)
export_image() {
    local output_file="${IMAGE_NAME}_${IMAGE_TAG}.tar"
    
    log_info "Esportazione immagine in: $output_file"
    docker save -o "$output_file" "$FULL_IMAGE_NAME" || {
        log_error "Esportazione immagine fallita"
        exit 1
    }
    
    local file_size=$(du -h "$output_file" | cut -f1)
    log_success "Immagine esportata: $output_file ($file_size)"
    echo
    log_info "Per trasferire su server remoto:"
    echo "  scp $output_file user@server:/path/"
    echo
    log_info "Per importare su server remoto:"
    echo "  docker load -i $output_file"
    echo "$output_file"
}

# Funzione per caricare l'immagine da file tar
import_image() {
    local tar_file="$1"
    
    if [[ ! -f "$tar_file" ]]; then
        log_error "File tar non trovato: $tar_file"
        exit 1
    fi
    
    log_info "Importazione immagine da: $tar_file"
    docker load -i "$tar_file" || {
        log_error "Importazione immagine fallita"
        exit 1
    }
    
    log_success "Immagine importata e disponibile localmente: $FULL_IMAGE_NAME"
}

# Funzione per mostrare informazioni sull'immagine
show_image_info() {
    echo
    log_info "=== INFORMAZIONI IMMAGINE ==="
    echo "• Nome completo: $FULL_IMAGE_NAME"
    echo "• Disponibile per docker-compose in Portainer"
    echo
    
    if docker images -q "$FULL_IMAGE_NAME" >/dev/null 2>&1; then
        echo "Dettagli immagine:"
        docker images "$FULL_IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}"
    else
        log_warning "Immagine non trovata nel sistema locale"
    fi
    echo
}

# Funzione per verificare che l'immagine sia utilizzabile
verify_image() {
    log_info "Verifica immagine..."
    
    # Test rapido dell'immagine - verifica dipendenze principali
    if docker run --rm "$FULL_IMAGE_NAME" python -c "import flask, requests, bs4; print('Dipendenze OK')" >/dev/null 2>&1; then
        log_success "Immagine verificata: dipendenze Python corrette"
    else
        log_warning "Verifica immagine fallita - controllare il Dockerfile"
        return 1
    fi
    
    # Test della struttura dell'applicazione
    if docker run --rm "$FULL_IMAGE_NAME" python -c "
import sys, os
sys.path.append('/app')
try:
    # Test import delle componenti principali
    from config import settings
    from services import indexer_service
    from models import episode, search_result
    from utils import helpers
    print('Struttura applicazione OK')
except ImportError as e:
    print(f'Errore import: {e}')
    sys.exit(1)
" >/dev/null 2>&1; then
        log_success "Struttura applicazione verificata"
    else
        log_warning "Verifica struttura applicazione fallita - alcuni moduli potrebbero non essere importabili"
    fi
}

# Funzione per mostrare l'help
show_help() {
    echo "Script di build Docker per MIRCrew Smart Indexer"
    echo
    echo "Uso: $0 [COMANDO]"
    echo
    echo "COMANDI:"
    echo "  build         Fa build dell'immagine Docker (default)"
    echo "  export        Esporta l'immagine in file tar per trasferimento"
    echo "  import FILE   Importa immagine da file tar"
    echo "  info          Mostra informazioni sull'immagine locale"
    echo "  verify        Verifica che l'immagine funzioni correttamente"
    echo "  clean         Rimuove l'immagine locale"
    echo "  help          Mostra questo messaggio"
    echo
    echo "ESEMPI:"
    echo "  $0                           # Build immagine locale"
    echo "  $0 export                    # Crea file tar per trasferimento"
    echo "  $0 import image.tar          # Importa da file tar"
    echo "  $0 info                      # Mostra dettagli immagine"
    echo
    echo "STRUTTURA PROGETTO RICHIESTA:"
    echo "  ├── app.py                   # Entry point applicazione"
    echo "  ├── Dockerfile               # Configurazione Docker"
    echo "  ├── config/                  # Configurazioni"
    echo "  ├── indexer/                 # Logica indexer"
    echo "  ├── models/                  # Modelli dati"
    echo "  ├── services/                # Servizi business logic"
    echo "  └── utils/                   # Utility e helpers"
    echo
    echo "FLUSSO TIPICO:"
    echo "  1. $0 build                  # Build locale"
    echo "  2. Usa docker-compose in Portainer con image: $FULL_IMAGE_NAME"
    echo
    echo "TRASFERIMENTO SU SERVER:"
    echo "  1. $0 export                 # Crea file tar"
    echo "  2. scp file.tar server:/     # Trasferisci"
    echo "  3. $0 import file.tar        # Importa su server"
    echo
}

# Funzione principale per build
do_build() {
    log_info "=== BUILD IMMAGINE DOCKER ==="
    
    check_docker
    check_files
    build_image
    verify_image
    show_image_info
    
    log_success "=== BUILD COMPLETATO ==="
    echo
    log_info "L'immagine è ora disponibile per docker-compose in Portainer"
    log_info "Usa: image: $FULL_IMAGE_NAME nel tuo docker-compose.yml"
}

# Switch per gestire i comandi
case "${1:-build}" in
    "build")
        do_build
        ;;
    
    "export")
        check_docker
        if ! docker images -q "$FULL_IMAGE_NAME" >/dev/null 2>&1; then
            log_error "Immagine $FULL_IMAGE_NAME non trovata. Esegui prima il build"
            exit 1
        fi
        export_image
        ;;
    
    "import")
        if [[ -z "$2" ]]; then
            log_error "Specificare il file tar da importare"
            log_info "Uso: $0 import <file.tar>"
            exit 1
        fi
        check_docker
        import_image "$2"
        show_image_info
        ;;
    
    "info")
        check_docker
        show_image_info
        ;;
    
    "verify")
        check_docker
        if ! docker images -q "$FULL_IMAGE_NAME" >/dev/null 2>&1; then
            log_error "Immagine $FULL_IMAGE_NAME non trovata. Esegui prima il build"
            exit 1
        fi
        verify_image
        ;;
    
    "clean")
        check_docker
        if docker images -q "$FULL_IMAGE_NAME" >/dev/null 2>&1; then
            log_warning "Rimozione immagine: $FULL_IMAGE_NAME"
            docker rmi "$FULL_IMAGE_NAME" || true
            log_success "Immagine rimossa"
        else
            log_info "Nessuna immagine da rimuovere"
        fi
        ;;
    
    "help"|"--help"|"-h")
        show_help
        ;;
    
    *)
        log_error "Comando sconosciuto: $1"
        show_help
        exit 1
        ;;
esac
